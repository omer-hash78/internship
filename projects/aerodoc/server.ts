import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import Database from "better-sqlite3";
import bcrypt from "bcryptjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Initialize SQLite database
const db = new Database("aerodoc.db");

// Create users table if it doesn't exist
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    status TEXT,
    authorId INTEGER,
    lastModified DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(authorId) REFERENCES users(id)
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS document_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documentId INTEGER,
    content TEXT,
    authorId INTEGER,
    versionNumber INTEGER,
    reasonForChange TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(documentId) REFERENCES documents(id),
    FOREIGN KEY(authorId) REFERENCES users(id)
  )
`);

try {
  db.exec("ALTER TABLE document_versions ADD COLUMN reasonForChange TEXT");
} catch (e) {
  // Column already exists
}

// Seed initial users if empty
const userCount = db.prepare("SELECT COUNT(*) as count FROM users").get() as { count: number };
if (userCount.count === 0) {
  const salt = bcrypt.genSaltSync(10);
  const adminPass = bcrypt.hashSync("password123", salt);
  const writerPass = bcrypt.hashSync("password123", salt);

  const insert = db.prepare("INSERT INTO users (username, password, role) VALUES (?, ?, ?)");
  insert.run("admin", adminPass, "Technical Lead");
  insert.run("writer", writerPass, "Technical Writer");
  console.log("Database seeded with default users.");

  // Seed initial documents
  const adminId = db.prepare("SELECT id FROM users WHERE username = 'admin'").get() as { id: number };
  const insertDoc = db.prepare("INSERT INTO documents (title, content, status, authorId) VALUES (?, ?, ?, ?)");
  insertDoc.run("F-35 Avionics Maintenance Manual", "Initial content for F-35 manual...", "Approved", adminId.id);
  insertDoc.run("Hydraulic System Spec v4.2", "Initial content for Hydraulic system...", "Review", adminId.id);
  insertDoc.run("Landing Gear Deployment Logic", "Initial content for Landing Gear...", "Draft", adminId.id);
}

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // Auth Endpoints
  app.post("/api/auth/login", (req, res) => {
    const { username, password } = req.body;
    
    try {
      const user = db.prepare("SELECT * FROM users WHERE username = ?").get(username) as any;
      
      if (user && bcrypt.compareSync(password, user.password)) {
        const { password: _, ...userWithoutPassword } = user;
        res.json({ success: true, user: userWithoutPassword });
      } else {
        res.status(401).json({ success: false, message: "Invalid credentials" });
      }
    } catch (err) {
      console.error("Login error:", err);
      res.status(500).json({ success: false, message: "Internal server error" });
    }
  });

  app.post("/api/auth/register", (req, res) => {
    const { username, password, role } = req.body;
    
    try {
      const salt = bcrypt.genSaltSync(10);
      const hashedPassword = bcrypt.hashSync(password, salt);
      
      const insert = db.prepare("INSERT INTO users (username, password, role) VALUES (?, ?, ?)");
      insert.run(username, hashedPassword, role || "Technical Writer");
      
      res.json({ success: true, message: "User registered successfully" });
    } catch (err: any) {
      if (err.code === "SQLITE_CONSTRAINT") {
        res.status(400).json({ success: false, message: "Username already exists" });
      } else {
        console.error("Registration error:", err);
        res.status(500).json({ success: false, message: "Internal server error" });
      }
    }
  });

  // Document Endpoints
  app.get("/api/documents", (req, res) => {
    try {
      const documents = db.prepare("SELECT * FROM documents ORDER BY lastModified DESC").all();
      res.json(documents);
    } catch (err) {
      res.status(500).json({ error: "Failed to fetch documents" });
    }
  });

  app.get("/api/documents/:id", (req, res) => {
    try {
      const document = db.prepare("SELECT * FROM documents WHERE id = ?").get(req.params.id);
      if (document) {
        res.json(document);
      } else {
        res.status(404).json({ error: "Document not found" });
      }
    } catch (err) {
      res.status(500).json({ error: "Failed to fetch document" });
    }
  });

  app.post("/api/documents", (req, res) => {
    const { title, content, status, authorId } = req.body;
    try {
      const info = db.prepare("INSERT INTO documents (title, content, status, authorId) VALUES (?, ?, ?, ?)").run(title, content, status, authorId);
      const docId = info.lastInsertRowid;
      
      // Create initial version
      db.prepare("INSERT INTO document_versions (documentId, content, authorId, versionNumber, reasonForChange) VALUES (?, ?, ?, ?, ?)").run(docId, content, authorId, 1, "Initial creation");
      
      res.json({ id: docId, success: true });
    } catch (err) {
      res.status(500).json({ error: "Failed to create document" });
    }
  });

  app.put("/api/documents/:id", (req, res) => {
    const { title, content, status, authorId, reasonForChange } = req.body;
    const docId = req.params.id;
    try {
      // Get current version number
      const lastVersion = db.prepare("SELECT MAX(versionNumber) as maxV FROM document_versions WHERE documentId = ?").get(docId) as { maxV: number };
      const nextVersion = (lastVersion.maxV || 0) + 1;

      // Update document
      db.prepare("UPDATE documents SET title = ?, content = ?, status = ?, lastModified = CURRENT_TIMESTAMP WHERE id = ?").run(title, content, status, docId);
      
      // Create new version
      db.prepare("INSERT INTO document_versions (documentId, content, authorId, versionNumber, reasonForChange) VALUES (?, ?, ?, ?, ?)").run(docId, content, authorId, nextVersion, reasonForChange || "Updated document");
      
      res.json({ success: true });
    } catch (err) {
      res.status(500).json({ error: "Failed to update document" });
    }
  });

  app.get("/api/documents/:id/versions", (req, res) => {
    try {
      const versions = db.prepare(`
        SELECT dv.*, u.username as authorName 
        FROM document_versions dv 
        JOIN users u ON dv.authorId = u.id 
        WHERE dv.documentId = ? 
        ORDER BY dv.versionNumber DESC
      `).all(req.params.id);
      res.json(versions);
    } catch (err) {
      res.status(500).json({ error: "Failed to fetch versions" });
    }
  });

  app.post("/api/documents/:id/revert", (req, res) => {
    const { versionId, authorId } = req.body;
    const docId = req.params.id;
    try {
      const version = db.prepare("SELECT * FROM document_versions WHERE id = ?").get(versionId) as any;
      if (!version) return res.status(404).json({ error: "Version not found" });

      // Get current version number
      const lastVersion = db.prepare("SELECT MAX(versionNumber) as maxV FROM document_versions WHERE documentId = ?").get(docId) as { maxV: number };
      const nextVersion = (lastVersion.maxV || 0) + 1;

      // Update document with version content
      db.prepare("UPDATE documents SET content = ?, lastModified = CURRENT_TIMESTAMP WHERE id = ?").run(version.content, docId);
      
      // Create new version for the revert action
      db.prepare("INSERT INTO document_versions (documentId, content, authorId, versionNumber, reasonForChange) VALUES (?, ?, ?, ?, ?)").run(docId, version.content, authorId, nextVersion, `Reverted to version ${version.versionNumber}`);
      
      res.json({ success: true });
    } catch (err) {
      res.status(500).json({ error: "Failed to revert document" });
    }
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`AeroDoc AI Server running on http://localhost:${PORT}`);
  });
}

startServer();

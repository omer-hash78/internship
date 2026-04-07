import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  ShieldCheck, 
  Cpu, 
  Search, 
  LogOut, 
  ChevronRight, 
  AlertTriangle, 
  CheckCircle,
  Loader2,
  Plus,
  History,
  RotateCcw,
  X,
  Edit3,
  Save,
  User as UserIcon,
  Eye
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { User, Document, ComplianceFinding, DocumentVersion } from './types';
import { analyzeCompliance, draftTechnicalSection } from './services/geminiService';

export default function App() {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [activeTab, setActiveTab] = useState<'docs' | 'compliance' | 'agent'>('docs');
  const [error, setError] = useState('');
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const [showViewer, setShowViewer] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Auth Logic
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (data.success) {
        setUser(data.user);
        localStorage.setItem('user', JSON.stringify(data.user));
      } else {
        setError(data.message);
      }
    } catch (err) {
      setError('Connection failed');
    }
  };

  const handleLogout = () => {
    setUser(null);
    setUsername('');
    setPassword('');
    localStorage.removeItem('user');
  };

  if (!user) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center p-4 font-sans text-white">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,#1A1A1C_0%,transparent_70%)] opacity-50" />
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md bg-[#151619] border border-[#2A2B2F] rounded-xl p-8 shadow-2xl relative z-10"
        >
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-blue-600 rounded flex items-center justify-center shadow-[0_0_15px_rgba(37,99,235,0.4)]">
              <Cpu className="text-white" size={24} />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">AERODOC AI</h1>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase mb-2">Personnel ID / Username</label>
              <input 
                type="text" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-[#0A0A0B] border border-[#2A2B2F] rounded px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                placeholder="Enter username"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase mb-2">Security Credential</label>
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#0A0A0B] border border-[#2A2B2F] rounded px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors text-sm"
                placeholder="Enter password"
                required
              />
            </div>
            {error && <p className="text-red-500 text-xs">{error}</p>}
            <button 
              type="submit"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded transition-all shadow-lg active:scale-[0.98]"
            >
              AUTHENTICATE
            </button>
          </form>
          
          <div className="mt-8 pt-6 border-t border-[#2A2B2F] text-center">
            <p className="text-[10px] text-gray-600 uppercase tracking-widest">
              Classified System Access • Authorized Personnel Only
            </p>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-gray-300 font-sans flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[#2A2B2F] bg-[#111214] flex flex-col">
        <div className="p-6 border-bottom border-[#2A2B2F]">
          <div className="flex items-center gap-3">
            <Cpu className="text-blue-500" size={24} />
            <span className="font-bold text-white tracking-tight">AERODOC AI</span>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          <NavItem 
            icon={<FileText size={18} />} 
            label="Documentation" 
            active={activeTab === 'docs'} 
            onClick={() => setActiveTab('docs')} 
          />
          <NavItem 
            icon={<ShieldCheck size={18} />} 
            label="Compliance" 
            active={activeTab === 'compliance'} 
            onClick={() => setActiveTab('compliance')} 
          />
          <NavItem 
            icon={<Cpu size={18} />} 
            label="AI Agent" 
            active={activeTab === 'agent'} 
            onClick={() => setActiveTab('agent')} 
          />
        </nav>

        <div className="p-4 border-t border-[#2A2B2F]">
          <div className="bg-[#1A1B1E] rounded-lg p-3 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-900 flex items-center justify-center text-blue-300 text-xs font-bold">
              {user.username[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-white truncate">{user.username}</p>
              <p className="text-[10px] text-gray-500 truncate">{user.role}</p>
            </div>
            <button onClick={handleLogout} className="text-gray-500 hover:text-white transition-colors">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-bottom border-[#2A2B2F] bg-[#111214] flex items-center justify-between px-8">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
            {activeTab === 'docs' && 'Technical Documentation Repository'}
            {activeTab === 'compliance' && 'S1000D Compliance Analysis'}
            {activeTab === 'agent' && 'Agentic Drafting Assistant'}
          </h2>
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={14} />
              <input 
                type="text" 
                placeholder="Search manuals..." 
                className="bg-[#0A0A0B] border border-[#2A2B2F] rounded-full py-1.5 pl-9 pr-4 text-xs focus:outline-none focus:border-blue-500 w-64"
              />
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-8">
          <AnimatePresence mode="wait">
            {activeTab === 'docs' && (
              <DocsView 
                key={`docs-${refreshKey}`}
                user={user} 
                onView={(doc) => {
                  setSelectedDoc(doc);
                  setShowViewer(true);
                }}
                onViewHistory={(doc) => {
                  setSelectedDoc(doc);
                  setShowHistory(true);
                }}
                onEdit={(doc) => {
                  setSelectedDoc(doc);
                  setShowEditor(true);
                }}
                onNew={() => {
                  setSelectedDoc({
                    id: 0,
                    title: 'Untitled Document',
                    content: '',
                    lastModified: new Date().toISOString(),
                    status: 'Draft',
                    authorId: user.id
                  });
                  setShowEditor(true);
                }}
              />
            )}
            {activeTab === 'compliance' && <ComplianceView key="compliance" />}
            {activeTab === 'agent' && <AgentView key="agent" />}
          </AnimatePresence>
        </div>

        {/* Modals */}
        <AnimatePresence>
          {showHistory && selectedDoc && (
            <VersionHistoryModal 
              doc={selectedDoc} 
              user={user}
              onClose={() => setShowHistory(false)} 
              onRevert={() => {
                setShowHistory(false);
                setRefreshKey(prev => prev + 1);
              }}
            />
          )}
          {showEditor && selectedDoc && (
            <DocumentEditorModal 
              doc={selectedDoc}
              user={user}
              onClose={() => setShowEditor(false)}
              onSave={() => {
                setShowEditor(false);
                setRefreshKey(prev => prev + 1);
              }}
            />
          )}
          {showViewer && selectedDoc && (
            <DocumentViewerModal 
              doc={selectedDoc}
              onClose={() => setShowViewer(false)}
            />
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}

function NavItem({ icon, label, active, onClick }: { icon: React.ReactNode, label: string, active: boolean, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-all ${
        active 
          ? 'bg-blue-600/10 text-blue-400 border border-blue-600/20' 
          : 'text-gray-500 hover:text-gray-300 hover:bg-[#1A1B1E]'
      }`}
    >
      {icon}
      <span className="font-medium">{label}</span>
      {active && <motion.div layoutId="active-pill" className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]" />}
    </button>
  );
}

function DocsView({ user, onView, onViewHistory, onEdit, onNew }: { key?: string, user: User, onView: (doc: Document) => void, onViewHistory: (doc: Document) => void, onEdit: (doc: Document) => void, onNew: () => void }) {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/documents');
      const data = await res.json();
      setDocs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-bold text-white">Recent Documents</h3>
        <button 
          onClick={onNew}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-bold transition-all"
        >
          <Plus size={16} />
          NEW DOCUMENT
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-48 bg-[#151619] animate-pulse rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {docs.map(doc => (
            <div key={doc.id} className="bg-[#151619] border border-[#2A2B2F] rounded-xl p-5 hover:border-blue-500/50 transition-all group relative">
              <div className="flex items-start justify-between mb-4">
                <div className="p-2 bg-blue-900/20 rounded-lg text-blue-400">
                  <FileText size={20} />
                </div>
                <div className="flex gap-2">
                  <button 
                    onClick={() => onView(doc)}
                    className="p-1.5 text-gray-500 hover:text-blue-400 transition-colors"
                    title="View Document"
                  >
                    <Eye size={16} />
                  </button>
                  <button 
                    onClick={() => onViewHistory(doc)}
                    className="p-1.5 text-gray-500 hover:text-blue-400 transition-colors"
                    title="Version History"
                  >
                    <History size={16} />
                  </button>
                  <button 
                    onClick={() => onEdit(doc)}
                    className="p-1.5 text-gray-500 hover:text-blue-400 transition-colors"
                    title="Edit Document"
                  >
                    <Edit3 size={16} />
                  </button>
                </div>
              </div>
              <h4 
                className="font-bold text-white mb-1 group-hover:text-blue-400 transition-colors cursor-pointer"
                onClick={() => onView(doc)}
              >
                {doc.title}
              </h4>
              <p className="text-xs text-gray-500">Modified: {new Date(doc.lastModified).toLocaleString()}</p>
              <div className="mt-4 pt-4 border-t border-[#2A2B2F] flex items-center justify-between">
                <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                  doc.status === 'Approved' ? 'bg-green-900/20 text-green-400' :
                  doc.status === 'Review' ? 'bg-yellow-900/20 text-yellow-400' :
                  'bg-blue-900/20 text-blue-400'
                }`}>
                  {doc.status}
                </span>
                <ChevronRight size={14} className="text-gray-600 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}

function VersionHistoryModal({ doc, user, onClose, onRevert }: { doc: Document, user: User, onClose: () => void, onRevert: () => void }) {
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVersions = async () => {
      try {
        const res = await fetch(`/api/documents/${doc.id}/versions`);
        const data = await res.json();
        setVersions(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchVersions();
  }, [doc.id]);

  const handleRevert = async (versionId: number) => {
    if (!confirm('Are you sure you want to revert to this version? A new version will be created.')) return;
    try {
      const res = await fetch(`/api/documents/${doc.id}/revert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ versionId, authorId: user.id })
      });
      if (res.ok) {
        onRevert();
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-[#151619] border border-[#2A2B2F] rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl"
      >
        <div className="p-6 border-b border-[#2A2B2F] flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-white">Version History</h3>
            <p className="text-xs text-gray-500">{doc.title}</p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="animate-spin text-blue-500" size={32} />
            </div>
          ) : (
            versions.map((v, idx) => (
              <div key={v.id} className="bg-[#1A1B1E] border border-[#2A2B2F] rounded-xl p-4 flex items-center justify-between group">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-blue-400 uppercase tracking-widest">Version {v.versionNumber}</span>
                    {idx === 0 && <span className="text-[10px] bg-blue-600/20 text-blue-400 px-1.5 py-0.5 rounded font-bold uppercase">Current</span>}
                  </div>
                  {v.reasonForChange && (
                    <p className="text-sm font-medium text-blue-300">Reason: {v.reasonForChange}</p>
                  )}
                  <p className="text-sm text-white line-clamp-1 opacity-60">{v.content}</p>
                  <div className="flex items-center gap-3 text-[10px] text-gray-500">
                    <span className="flex items-center gap-1"><UserIcon size={10} /> {v.authorName}</span>
                    <span>{new Date(v.createdAt).toLocaleString()}</span>
                  </div>
                </div>
                {idx !== 0 && (
                  <button 
                    onClick={() => handleRevert(v.id)}
                    className="flex items-center gap-2 bg-[#2A2B2F] hover:bg-blue-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-all opacity-0 group-hover:opacity-100"
                  >
                    <RotateCcw size={14} />
                    REVERT
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </motion.div>
    </div>
  );
}

function DocumentViewerModal({ doc, onClose }: { doc: Document, onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-[#151619] border border-[#2A2B2F] rounded-2xl w-full max-w-4xl h-[90vh] flex flex-col shadow-2xl"
      >
        <div className="p-6 border-b border-[#2A2B2F] flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-white">{doc.title}</h3>
            <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
              <span className={`font-bold uppercase px-2 py-0.5 rounded ${
                doc.status === 'Approved' ? 'bg-green-900/20 text-green-400' :
                doc.status === 'Review' ? 'bg-yellow-900/20 text-yellow-400' :
                'bg-blue-900/20 text-blue-400'
              }`}>
                {doc.status}
              </span>
              <span>Modified: {new Date(doc.lastModified).toLocaleString()}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-3xl mx-auto whitespace-pre-wrap font-mono text-sm text-gray-300 leading-relaxed">
            {doc.content}
          </div>
        </div>

        <div className="p-6 border-t border-[#2A2B2F] flex justify-end">
          <button 
            onClick={onClose}
            className="bg-[#2A2B2F] hover:bg-[#3A3B3F] text-white px-6 py-2 rounded-lg text-sm font-bold transition-all"
          >
            CLOSE
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function DocumentEditorModal({ doc, user, onClose, onSave }: { doc: Document, user: User, onClose: () => void, onSave: () => void }) {
  const [title, setTitle] = useState(doc.title);
  const [content, setContent] = useState(doc.content);
  const [status, setStatus] = useState(doc.status);
  const [reasonForChange, setReasonForChange] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      const isNew = doc.id === 0;
      const url = isNew ? '/api/documents' : `/api/documents/${doc.id}`;
      const method = isNew ? 'POST' : 'PUT';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, content, status, authorId: user.id, reasonForChange })
      });
      if (res.ok) {
        onSave();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-[#151619] border border-[#2A2B2F] rounded-2xl w-full max-w-4xl h-[90vh] flex flex-col shadow-2xl"
      >
        <div className="p-6 border-b border-[#2A2B2F] flex items-center justify-between">
          <h3 className="text-lg font-bold text-white">Edit Document</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col p-6 gap-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase">Document Title</label>
              <input 
                type="text" 
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-[#0A0A0B] border border-[#2A2B2F] rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase">Status</label>
              <select 
                value={status}
                onChange={(e) => setStatus(e.target.value as any)}
                className="w-full bg-[#0A0A0B] border border-[#2A2B2F] rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
              >
                <option value="Draft">Draft</option>
                <option value="Review">Review</option>
                <option value="Approved">Approved</option>
              </select>
            </div>
          </div>

          <div className="flex-1 flex flex-col space-y-2">
            <label className="text-xs font-bold text-gray-400 uppercase">Content</label>
            <textarea 
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="flex-1 bg-[#0A0A0B] border border-[#2A2B2F] rounded-xl p-4 text-sm focus:outline-none focus:border-blue-500 resize-none font-mono leading-relaxed"
            />
          </div>

          {doc.id !== 0 && (
            <div className="space-y-2">
              <label className="text-xs font-bold text-gray-400 uppercase">Reason for Change (Required)</label>
              <input 
                type="text" 
                value={reasonForChange}
                onChange={(e) => setReasonForChange(e.target.value)}
                placeholder="e.g., Updated torque specs per Service Bulletin 123"
                className="w-full bg-[#0A0A0B] border border-[#2A2B2F] rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500"
              />
            </div>
          )}
        </div>

        <div className="p-6 border-t border-[#2A2B2F] flex justify-end gap-3">
          <button 
            onClick={onClose}
            className="px-6 py-2 rounded-lg text-sm font-bold text-gray-400 hover:text-white transition-colors"
          >
            CANCEL
          </button>
          <button 
            onClick={handleSave}
            disabled={saving || (doc.id !== 0 && !reasonForChange.trim())}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-8 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all"
          >
            {saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
            SAVE CHANGES
          </button>
        </div>
      </motion.div>
    </div>
  );
}

function ComplianceView() {
  const [text, setText] = useState('');
  const [findings, setFindings] = useState<ComplianceFinding[]>([]);
  const [loading, setLoading] = useState(false);
  const [docs, setDocs] = useState<Document[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('');

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const res = await fetch('/api/documents');
        const data = await res.json();
        setDocs(data);
      } catch (err) {
        console.error(err);
      }
    };
    fetchDocs();
  }, []);

  const handleDocSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const docId = e.target.value;
    setSelectedDocId(docId);
    if (docId) {
      const doc = docs.find(d => d.id.toString() === docId);
      if (doc) {
        setText(doc.content);
      }
    } else {
      setText('');
    }
  };

  const handleAnalyze = async () => {
    if (!text) return;
    setLoading(true);
    try {
      const result = await analyzeCompliance(text);
      setFindings(result.findings || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full"
    >
      <div className="flex flex-col gap-4">
        <h3 className="text-xl font-bold text-white">Compliance Scanner</h3>
        <p className="text-sm text-gray-500">Select an existing document or paste technical text below to check against aerospace standards.</p>
        
        <select 
          value={selectedDocId}
          onChange={handleDocSelect}
          className="bg-[#151619] border border-[#2A2B2F] rounded-xl p-3 text-sm text-white focus:outline-none focus:border-blue-500"
        >
          <option value="">-- Select an existing document --</option>
          {docs.map(doc => (
            <option key={doc.id} value={doc.id}>{doc.title}</option>
          ))}
        </select>

        <textarea 
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setSelectedDocId(''); // Clear selection if user manually edits
          }}
          className="flex-1 bg-[#151619] border border-[#2A2B2F] rounded-xl p-4 text-sm focus:outline-none focus:border-blue-500 resize-none font-mono"
          placeholder="Enter technical procedure or specification text..."
        />
        <button 
          onClick={handleAnalyze}
          disabled={loading || !text}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 transition-all"
        >
          {loading ? <Loader2 className="animate-spin" size={18} /> : <ShieldCheck size={18} />}
          RUN COMPLIANCE SCAN
        </button>
      </div>

      <div className="flex flex-col gap-4">
        <h3 className="text-xl font-bold text-white">Analysis Results</h3>
        <div className="flex-1 bg-[#111214] border border-[#2A2B2F] rounded-xl overflow-y-auto p-4 space-y-4">
          {findings.length === 0 && !loading && (
            <div className="h-full flex flex-col items-center justify-center text-gray-600 text-center p-8">
              <ShieldCheck size={48} className="mb-4 opacity-20" />
              <p className="text-sm">No analysis run yet. Enter text and start scan.</p>
            </div>
          )}
          
          {loading && (
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-24 bg-[#1A1B1E] animate-pulse rounded-lg" />
              ))}
            </div>
          )}

          {findings.map((finding, idx) => (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              key={idx} 
              className={`p-4 rounded-lg border ${
                finding.severity === 'high' ? 'bg-red-900/10 border-red-900/30' :
                finding.severity === 'medium' ? 'bg-yellow-900/10 border-yellow-900/30' :
                'bg-blue-900/10 border-blue-900/30'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {finding.severity === 'high' ? <AlertTriangle className="text-red-500" size={14} /> :
                 finding.severity === 'medium' ? <AlertTriangle className="text-yellow-500" size={14} /> :
                 <CheckCircle className="text-blue-500" size={14} />}
                <span className={`text-[10px] font-bold uppercase ${
                  finding.severity === 'high' ? 'text-red-400' :
                  finding.severity === 'medium' ? 'text-yellow-400' :
                  'text-blue-400'
                }`}>
                  {finding.severity} SEVERITY
                </span>
              </div>
              <p className="text-sm font-bold text-white mb-1">{finding.issue}</p>
              <p className="text-xs text-gray-400 italic">Suggestion: {finding.suggestion}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

function AgentView() {
  const [topic, setTopic] = useState('');
  const [specs, setSpecs] = useState('');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  const handleDraft = async () => {
    if (!topic || !specs) return;
    setLoading(true);
    try {
      const text = await draftTechnicalSection(topic, specs);
      setResult(text || '');
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="max-w-4xl mx-auto space-y-8"
    >
      <div className="text-center space-y-2">
        <h3 className="text-2xl font-bold text-white">Agentic Drafting Assistant</h3>
        <p className="text-gray-500">Generate high-precision technical documentation sections using AI.</p>
      </div>

      <div className="bg-[#151619] border border-[#2A2B2F] rounded-2xl p-8 space-y-6 shadow-xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="text-xs font-bold text-gray-400 uppercase">System / Component Topic</label>
            <input 
              type="text" 
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Auxiliary Power Unit (APU) Startup"
              className="w-full bg-[#0A0A0B] border border-[#2A2B2F] rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-bold text-gray-400 uppercase">Technical Specifications</label>
            <input 
              type="text" 
              value={specs}
              onChange={(e) => setSpecs(e.target.value)}
              placeholder="e.g. 28V DC, 400Hz AC, Max Temp 750C"
              className="w-full bg-[#0A0A0B] border border-[#2A2B2F] rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <button 
          onClick={handleDraft}
          disabled={loading || !topic || !specs}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold py-4 rounded-xl flex items-center justify-center gap-3 transition-all shadow-lg"
        >
          {loading ? <Loader2 className="animate-spin" size={20} /> : <Cpu size={20} />}
          GENERATE TECHNICAL DRAFT
        </button>

        {result && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 space-y-4"
          >
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Generated Output</h4>
              <button 
                onClick={() => navigator.clipboard.writeText(result)}
                className="text-[10px] text-blue-400 hover:text-blue-300 font-bold uppercase"
              >
                Copy to Clipboard
              </button>
            </div>
            <div className="bg-[#0A0A0B] border border-[#2A2B2F] rounded-xl p-6 text-sm text-gray-300 font-mono whitespace-pre-wrap leading-relaxed">
              {result}
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}

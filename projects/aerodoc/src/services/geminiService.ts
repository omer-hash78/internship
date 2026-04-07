import { GoogleGenAI } from "@google/genai";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || "" });

export const geminiModel = "gemini-3-flash-preview";

export async function analyzeCompliance(text: string) {
  const response = await ai.models.generateContent({
    model: geminiModel,
    contents: `Analyze the following technical documentation for aerospace compliance (S1000D/MIL-STD). Identify potential issues, safety concerns, and consistency errors. Return a JSON object with a list of "findings", each having "severity" (low, medium, high), "issue", and "suggestion".
    
    Text: ${text}`,
    config: {
      responseMimeType: "application/json",
    }
  });
  return JSON.parse(response.text || "{}");
}

export async function draftTechnicalSection(topic: string, specs: string) {
  const response = await ai.models.generateContent({
    model: geminiModel,
    contents: `Draft a technical documentation section for an aerospace system. 
    Topic: ${topic}
    Specifications: ${specs}
    Style: Professional, concise, following aerospace technical writing standards. Use clear headings and bullet points where appropriate.`,
  });
  return response.text;
}

export async function technicalQuery(query: string, context: string) {
  const response = await ai.models.generateContent({
    model: geminiModel,
    contents: `You are an expert aerospace technical documentation assistant. Answer the user's query based on the provided technical context.
    
    Context: ${context}
    Query: ${query}`,
  });
  return response.text;
}

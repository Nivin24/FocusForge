// frontend/src/App.tsx
// FINAL WORKING VERSION — Private User ID + YouTube Cards + No Errors
import React, { useState, useRef, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import { Upload, FileText, Send, Sparkles } from 'lucide-react';

interface Message {
  type: 'user' | 'ai' | 'system';
  text: string;
  sources?: any[];
}

interface UploadedFile {
  filename: string;
  uploaded_at: string;
}

// PRIVATE USER ID — EVERY USER HAS THEIR OWN NOTES
const getUserId = (): string => {
  let id = localStorage.getItem('focusforge_user_id');
  if (!id) {
    id = 'user_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    localStorage.setItem('focusforge_user_id', id);
  }
  return id;
};

const userId = getUserId();

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    { type: 'system', text: 'No notes uploaded yet. Upload a PDF or text file first!' }
  ]);
  const [asking, setAsking] = useState(false);
  const [input, setInput] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load file history for THIS user only
  const loadFileHistory = async () => {
    try {
      const res = await axios.get('http://127.0.0.1:5000/api/files', {
        params: { user_id: userId }
      });
      setUploadedFiles(res.data.files || []);
    } catch (err) {
      console.log("No files yet for this user");
    }
  };

  useEffect(() => {
    loadFileHistory();
  }, []);

  const onDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const formData = new FormData();
    acceptedFiles.forEach(file => formData.append('file', file));

    try {
      const res = await axios.post('http://127.0.0.1:5000/api/upload', formData, {
        params: { user_id: userId }
      });

      const action = res.data.action === "replaced" ? "Updated" : "Added";
      const filename = res.data.filename;
      const time = res.data.uploaded_at;

      setMessages(prev => [...prev, { 
        type: 'system', 
        text: `${action}: ${filename} • ${time}` 
      }]);

      loadFileHistory();

    } catch (err: any) {
      const errorMsg = err.response?.data?.error || err.message || "Upload failed";
      setMessages(prev => [...prev, { type: 'system', text: `Upload failed: ${errorMsg}` }]);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 
      'application/pdf': ['.pdf'], 
      'text/plain': ['.txt'],
      'text/markdown': ['.md']
    }
  });

  const sendQuestion = async () => {
    if (!input.trim() || asking) return;

    const userMsg = input.trim();
    setMessages(prev => [...prev, { type: 'user', text: userMsg }]);
    setInput('');
    setAsking(true);

    try {
      const res = await axios.post('http://127.0.0.1:5000/api/ask', {
        question: userMsg,
        user_id: userId
      });

      setMessages(prev => [...prev, {
        type: 'ai',
        text: res.data.answer,
        sources: res.data.sources
      }]);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        type: 'ai',
        text: 'Sorry, something went wrong. Please try again.'
      }]);
    } finally {
      setAsking(false);
    }
  };

  return (
    <>
      <div className="flex h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 text-white">
        {/* LEFT SIDEBAR */}
        <div className="w-80 bg-black/30 backdrop-blur-xl border-r border-white/10 flex flex-col">
          <div className="p-6 border-b border-white/10">
            <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              FocusForge
            </h1>
            <p className="text-sm text-purple-200 mt-1">Your Personal RAG Study Assistant</p>
          </div>

          <div className="p-6">
            <div {...getRootProps()} className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all
              ${isDragActive ? 'border-purple-400 bg-purple-400/10' : 'border-white/30 hover:border-purple-400'}`}>
              <input {...getInputProps()} />
              <Upload className="w-12 h-12 mx-auto mb-4 text-purple-400" />
              <p className="text-lg font-medium">Drop files here</p>
              <p className="text-sm text-gray-400 mt-2">PDF, TXT, MD • Re-upload to update</p>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4">
            <h3 className="text-xs font-semibold text-purple-300 uppercase tracking-wider mb-3 px-2">
              Your Notes ({uploadedFiles.length})
            </h3>
            {uploadedFiles.length === 0 ? (
              <p className="text-center text-gray-500 text-sm mt-8">No files uploaded yet</p>
            ) : (
              <div className="space-y-2">
                {uploadedFiles.map((file, i) => (
                  <div key={i} className="group bg-white/5 hover:bg-white/10 rounded-xl p-4 transition-all border border-white/5">
                    <div className="flex items-start gap-3">
                      <FileText className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{file.filename}</p>
                        <p className="text-xs text-gray-400 mt-1">Uploaded: {file.uploaded_at}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* MAIN CHAT */}
        <div className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto px-6 py-8">
            <div className="max-w-4xl mx-auto space-y-6">
              {messages.length === 1 && messages[0].type === 'system' && (
                <div className="text-center py-20">
                  <Sparkles className="w-16 h-16 mx-auto mb-6 text-purple-400 opacity-50" />
                  <p className="text-xl text-gray-400">Upload your notes and start asking questions!</p>
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`${msg.type === 'user' ? 'text-right' : 'text-left'}`}>
                  <div className={`inline-block max-w-4xl rounded-3xl px-6 py-4 ${
                    msg.type === 'user' 
                      ? 'bg-gradient-to-r from-purple-600 to-pink-600' 
                      : msg.type === 'ai'
                      ? 'bg-white/10 backdrop-blur-xl border border-white/10'
                      : 'bg-green-500/20 border border-green-400/30'
                  }`}>
                    {/* Main Answer */}
                    <div className="whitespace-pre-wrap text-lg leading-relaxed mb-4">
                      {msg.text.includes('**Recommended Videos:**') 
                        ? msg.text.split('**Recommended Videos:**')[0].trim()
                        : msg.text
                      }
                    </div>

                    {/* Sources */}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-white/20">
                        <p className="text-xs opacity-75 mb-2">Sources:</p>
                        
                        {/* Step 1: Extract source names safely */}
                        {(() => {
                          const sources = msg.sources.map((s: any) => s.source || "Note");

                          // Step 2: Get only unique values
                          const uniqueSources = [...new Set(sources)];

                          return (
                            <div className="flex flex-wrap gap-2">
                              {uniqueSources.map((source: string, index: number) => (
                                <span key={index} className="text-xs bg-white/10 px-3 py-1 rounded-full">
                                  {source}
                                </span>
                              ))}
                            </div>
                          );
                        })()}
                      </div>
                    )}

                    {/* YouTube Cards */}
                    {msg.text.includes('**Recommended Videos:**') && (
                      <div className="mt-8 pt-6 border-t border-white/10">
                        <p className="text-xl font-bold text-purple-300 mb-6">
                          Recommended Videos
                        </p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                          {msg.text
                            .split('**Recommended Videos:**')[1]
                            .trim()
                            .split('\n')
                            .filter(line => line.includes('watch?v='))
                            .map((line, idx) => {
                              const match = line.match(/watch\?v=([a-zA-Z0-9_-]{11})/);
                              if (!match) return null;
                              const videoId = match[1];

                              return (
                                <a
                                  key={idx}
                                  href={`https://www.youtube.com/watch?v=${videoId}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="block group transform transition-all duration-300 hover:scale-105"
                                >
                                  <div className="bg-white/10 backdrop-blur-xl rounded-2xl overflow-hidden border border-white/20 shadow-2xl">
                                    <div className="relative">
                                      <img
                                        src={`https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`}
                                        alt="YouTube video"
                                        className="w-full h-52 object-cover"
                                        onError={(e) => {
                                          e.currentTarget.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
                                        }}
                                      />
                                      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                                        <div className="text-6xl text-white">Play</div>
                                      </div>
                                    </div>
                                    <div className="p-5">
                                      <p className="text-purple-200 font-medium group-hover:text-white transition">
                                        Watch Explanation on YouTube
                                      </p>
                                      <p className="text-sm text-purple-300 mt-2">Click to open</p>
                                    </div>
                                  </div>
                                </a>
                              );
                            })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {asking && (
                <div className="text-left">
                  <div className="inline-block rounded-3xl px-6 py-4 bg-white/10 backdrop-blur-xl border border-white/10">
                    <div className="flex items-center gap-3">
                      <div className="animate-spin rounded-full h-5 w-5 border-2 border-purple-400 border-t-transparent"></div>
                      <span>Thinking with Gemini 2.5...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input */}
          <div className="border-t border-white/10 bg-black/30 backdrop-blur-xl">
            <div className="max-w-4xl mx-auto p-6">
              <div className="flex gap-4">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendQuestion()}
                  placeholder="Ask anything about your notes..."
                  className="flex-1 bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl px-6 py-4 text-lg focus:outline-none focus:border-purple-400 transition-all placeholder-gray-400"
                />
                <button
                  onClick={sendQuestion}
                  disabled={asking || !input.trim()}
                  className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-2xl px-8 py-4 font-semibold flex items-center gap-3 transition-all"
                >
                  <Send className="w-5 h-5" />
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
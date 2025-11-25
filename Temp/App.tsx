// frontend/src/App.tsx
// FINAL WORKING VERSION — Private User ID + YouTube Cards + No Errors
import { useState, useRef, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';
import { Upload,Search, FileText, X, Send, Sparkles, Trash2 } from 'lucide-react';
import { BookOpen, Zap, HelpCircle, Map, Mic, Lightbulb, Trophy, Volume2, VolumeX } from 'lucide-react';

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
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000" ;


const userId = getUserId();


export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [autoSpeak, setAutoSpeak] = useState(false); // default ON (most users love it)
  const modeLabels: Record<string, string> = {
    study: "Study Focus",
    quick: "Quick Revision",
    quiz: "Quiz Master",
    roadmap: "Roadmap Builder",
    doubt: "Doubt Solver",
    strategy: "Exam Strategy"
  };

  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-IN';

    let finalTranscript = '';

    recognition.onresult = (event: any) => {
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcriptPart = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcriptPart + ' ';
        } else {
          interimTranscript += transcriptPart;
        }
      }

      setTranscript(finalTranscript + interimTranscript);

      // Auto-send when user says "send", "go", "submit"
      const lower = (finalTranscript + interimTranscript).toLowerCase();
      if (lower.includes('send') || lower.includes('go') || lower.includes('submit')) {
        stopListening();
        setUserMsg(finalTranscript.replace(/send|go|submit/gi, '').trim());
        sendMessage();
      }
    };

    recognition.onerror = (event: any) => {
      console.log("Speech error:", event.error);
      if (event.error === 'not-allowed') {
        alert("Microphone access denied");
      }
      setIsListening(false);
    };

    recognition.onend = () => {
      // THIS IS THE KEY FIX: Restart if user was still listening
      if (isListening) {
        recognition.start(); // ← PREVENTS RANDOM STOPPING
      }
      setIsListening(false);
    };

    return () => {
      recognition.stop();
    };
  }, [isListening]); // ← Restart when isListening changes


  // ADD THIS useEffect — FIX VOICE LOADING
  useEffect(() => {
    if ('speechSynthesis' in window) {
      const loadVoices = () => {
        window.speechSynthesis.getVoices();
      };
      window.speechSynthesis.onvoiceschanged = loadVoices;
      loadVoices();
    }
  }, []);

  // Start & Stop Functions
  const startListening = () => {
    if (recognitionRef.current) {
      setTranscript('');
      recognitionRef.current.start();
      setIsListening(true);
    }
  };

  const speakAnswer = (text: string) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel(); // Stop any current speech

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      utterance.pitch = 1.1;
      
      // Try to get Indian/British female voice
      const voices = window.speechSynthesis.getVoices();
      const preferredVoice = voices.find(v => 
        v.name.includes('Google UK English Female')  // ||
        // v.name.includes('Google हिन्दी') ||
        // v.lang.includes('en-IN') ||
        // v.lang.includes('en-GB')
      );
      
      if (preferredVoice) utterance.voice = preferredVoice;

      utterance.onend = () => console.log("Finished speaking");
      utterance.onerror = (e) => console.log("Speech error:", e);

      window.speechSynthesis.speak(utterance);
    }
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
      if (transcript.trim()) {
        setUserMsg(transcript.trim());
      }
    }
  };
  

  // Load files on start → then decide what message to show
  useEffect(() => {
    const initialize = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/files`, {
          params: { user_id: userId }
        });
        const files = res.data.files || [];

        setUploadedFiles(files);

        if (files.length === 0) {
          setMessages([
            { type: 'system', text: 'No notes uploaded yet. Upload a PDF or text file first!' }
          ]);
        } else {
          setMessages([
            { type: 'system', text: `Welcome back! You have ${files.length} note(s) ready.` }
          ]);
        }
      } catch (err) {
        setMessages([
          { type: 'system', text: 'No notes uploaded yet. Upload a PDF or text file first!' }
        ]);
      }
    };

    initialize();
  }, []);
  const [asking, setAsking] = useState(false);
  const [userMsg, setUserMsg] = useState('');   // ← MATCHES THE INPUT FIELD
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteCandidate, setDeleteCandidate] = useState<UploadedFile | null>(null);
  const [selectedMode, setSelectedMode] = useState("study");

  const filteredFiles = uploadedFiles.filter(file =>
    file.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load file history for THIS user only
  const loadFileHistory = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/files`, {
        params: { user_id: userId }
      });
      setUploadedFiles(res.data.files || []);
    } catch (err) {
      console.log("No files yet for this user");
    }
  };

  // useEffect(() => {
  //   loadFileHistory();
  // }, []);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, []);

  const onDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(
        `${API_URL}/api/upload?user_id=${userId}`,
        formData,
        {
          timeout: 300000, 
          // NO HEADERS — THIS IS CORRECT
        }
      );

      const { filename, action } = response.data;
      const actionText = action === "replaced" ? "Updated" : "Uploaded";

      setMessages(prev => [...prev, {
        type: "system",
        text: `${actionText}: ${filename}`,
      }]);

      loadFileHistory();

    } catch (err: any) {
      console.error("Upload error:", err);
      setMessages(prev => [...prev, {
        type: "system",
        text: `Upload failed: ${err.message}`,
      }]);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 
      'application/pdf': ['.pdf'], 
      'text/plain': ['.txt'],
      'text/markdown': ['.md']
    },
    multiple: false,
    maxSize: 100 * 1024 * 1024, // 100MB limit
  });

  const sendMessage = async () => {
    if (!userMsg.trim() || asking) return;

    const questionText = userMsg.trim();

    // Add user message
    setMessages(prev => [...prev, { type: 'user', text: questionText }]);

    // DO NOT add any "Thinking..." bubble here → keep UI clean
    setUserMsg('');
    setAsking(true);  // This triggers your existing loading animation at bottom

    try {
      const res = await axios.post(`${API_URL}/api/ask`, {
        question: questionText,
        user_id: userId,
        mode: selectedMode
      });

      // Directly add the real answer (no intermediate "Thinking..." bubble)
      setMessages(prev => [...prev, {
        type: 'ai',
        text: res.data.answer,
        sources: res.data.sources || []
      }]);

      // ONLY SPEAK IF USER WANTS
      if (autoSpeak) {
        speakAnswer(res.data.answer);
      }

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
        {/* LEFT SIDEBAR — FINAL PREMIUM VERSION */}
        <div className="w-80 bg-black/30 backdrop-blur-xl border-r border-white/10 flex flex-col">
          <div className="p-6 border-b border-white/10">
            <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              FocusForge
            </h1>
            <p className="text-sm text-purple-200 mt-1">Your Personal RAG Study Assistant</p>
          </div>

          {/* UPLOAD ZONE */}
          <div className="p-6">
            <div {...getRootProps()} className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all
              ${isDragActive ? 'border-purple-400 bg-purple-400/10' : 'border-white/30 hover:border-purple-400'}`}>
              <input {...getInputProps()} />
              <Upload className="w-12 h-12 mx-auto mb-4 text-purple-400" />
              <p className="text-lg font-medium">Drop files here</p>
              <p className="text-sm text-gray-400 mt-2">PDF, TXT, MD <br />Re-upload to update</p>
            </div>
          </div>

          {/* SEARCH + YOUR NOTES HEADER */}
          <div className="px-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className={`text-xs font-semibold text-purple-300 uppercase tracking-wider transition-all duration-300 ${
                isSearchOpen ? 'opacity-0 translate-x-[-20px]' : 'opacity-100'
              }`}>
                Your Notes ({uploadedFiles.length})
              </h3>

              {/* Search Icon */}
              {!isSearchOpen && (
                <button
                  onClick={() => setIsSearchOpen(true)}
                  className="p-1.5 hover:bg-white/10 rounded-lg transition opacity-70 hover:opacity-100"
                  title="Press Cmd + / or Ctrl + /"
                >
                  <Search className="w-4 h-4 text-purple-300" />
                </button>
              )}
            </div>

            {/* SEARCH BAR — slides in */}
            <div className={`relative overflow-hidden transition-all duration-300 ${
              isSearchOpen ? 'max-h-20 opacity-100 mb-4' : 'max-h-0 opacity-0 mb-0'
            }`}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Escape' && setIsSearchOpen(false)}
                placeholder="Search your notes..."
                autoFocus
                className="w-full bg-white/10 backdrop-blur-xl border border-white/20 rounded-xl px-4 py-3 pr-10 text-sm focus:outline-none focus:border-purple-400 transition-all placeholder-gray-400"
              />
              <button
                onClick={() => {
                  setIsSearchOpen(false);
                  setSearchQuery('');
                }}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 hover:bg-white/10 rounded-lg transition"
              >
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          </div>

          {/* FILE LIST */}
          <div className="flex-1 overflow-y-auto px-4">
            {filteredFiles.length === 0 ? (
              <p className="text-center text-gray-500 text-sm mt-8">
                {searchQuery ? 'No notes found' : 'No files uploaded yet'}
              </p>
            ) : (
              <div className="space-y-2">
                {filteredFiles.map((file) => (
                  <div
                    key={file.filename}
                    className="group bg-white/5 hover:bg-white/10 rounded-xl p-4 transition-all border border-white/5 flex items-center justify-between"
                  >
                    {/* File Info */}
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <FileText className="w-5 h-5 text-purple-400 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="font-medium text-sm truncate">{file.filename}</p>
                        <p className="text-xs text-gray-400">Uploaded: {file.uploaded_at}</p>
                      </div>
                    </div>

                    {/* Delete Button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteCandidate(file);
                      }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-red-500/20 rounded-lg"
                    >
                      <Trash2 className="w-4 h-4 text-red-400" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* GLOBAL DELETE MODAL — OUTSIDE THE MAP */}
        {deleteCandidate && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-gray-900/90 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl max-w-sm w-full p-6">
              <div className="flex items-center gap-4 mb-6">
                <div className="p-3 bg-red-500/20 rounded-xl">
                  <Trash2 className="w-8 h-8 text-red-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">Delete File?</h3>
                  <p className="text-sm text-gray-400 mt-1">This action cannot be undone</p>
                </div>
              </div>

              <div className="bg-white/5 rounded-xl p-4 mb-6">
                <p className="text-sm font-medium text-purple-300 truncate">
                  {deleteCandidate.filename}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Uploaded: {deleteCandidate.uploaded_at}
                </p>
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setDeleteCandidate(null)}
                  className="px-6 py-3 bg-white/10 hover:bg-white/20 rounded-xl font-medium transition"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    try {
                      await axios.post(`${API_URL}/api/delete_file`, {
                        user_id: userId,
                        filename: deleteCandidate.filename
                      });
                      setMessages(prev => [...prev, { type: 'system', text: `Deleted: ${deleteCandidate.filename}` }]);
                      loadFileHistory();
                    } catch (err) {
                      alert("Delete failed. Check console.");
                      console.error(err);
                    } finally {
                      setDeleteCandidate(null);
                    }
                  }}
                  className="px-6 py-3 bg-gradient-to-r from-red-600 to-pink-600 hover:from-red-500 hover:to-pink-500 rounded-xl font-medium transition shadow-lg"
                >
                  Delete Permanently
                </button>
              </div>
            </div>
          </div>
        )}

        {/* MAIN CHAT */}
        <div className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto px-6 py-8">
            <div className="max-w-4xl mx-auto space-y-6">
              {uploadedFiles.length > 0 ? (
                <div className="text-center py-20">
                  <Sparkles className="w-16 h-16 mx-auto mb-6 text-purple-400 opacity-80" />
                  <p className="text-2xl font-bold text-purple-300">Welcome back!</p>
                  <p className="text-lg text-gray-300 mt-2">
                    You have <span className="text-purple-400 font-bold">{uploadedFiles.length}</span> note{uploadedFiles.length > 1 ? 's' : ''} ready
                  </p>
                  <p className="text-md text-gray-400 mt-4">Ask anything — I'm ready!</p>
                </div>
              ) : (
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
                    <div className="whitespace-pre-wrap text-lg leading-relaxed">
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

          {/* MODE SELECTOR + INPUT BAR — PREMIUM LOOK */}
          <div className="border-t border-white/10 bg-black/30 backdrop-blur-xl p-4">
            {/* MODE SELECTOR */}
            <div className="flex flex-wrap gap-2 mb-4 justify-center">
              {[
                { id: "study", label: "Study Focus", icon: BookOpen, color: "from-purple-500 to-pink-500" },
                { id: "quick", label: "Quick Revision", icon: Zap, color: "from-yellow-500 to-orange-500" },
                { id: "quiz", label: "Quiz Master", icon: HelpCircle, color: "from-blue-500 to-cyan-500" },
                { id: "roadmap", label: "Roadmap Builder", icon: Map, color: "from-green-500 to-emerald-500" },
                { id: "doubt", label: "Doubt Solver", icon: Lightbulb, color: "from-orange-500 to-red-500" },
                { id: "strategy", label: "Exam Strategy", icon: Trophy, color: "from-pink-500 to-rose-500" },
              ].map((mode) => (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium text-sm transition-all transform hover:scale-105 ${
                    selectedMode === mode.id
                      ? `bg-gradient-to-r ${mode.color} text-white shadow-lg ring-4 ring-white/20`
                      : "bg-white/10 text-gray-300 hover:bg-white/20"
                  }`}
                >
                  <mode.icon className="w-5 h-5" />
                  {mode.label}
                </button>
              ))}
            </div>
            {/* AUTO-SPEAK TOGGLE — PREMIUM LOOK */}


            {/* CURRENT MODE INDICATOR */}
            <div className="text-center mb-3">
              <p className="text-xs text-gray-400">
                Active Mode: {" "}
                <span className="font-bold text-purple-300">
                  {selectedMode === "study" && "Study Focus"}
                  {selectedMode === "quick" && "Quick Revision"}
                  {selectedMode === "quiz" && "Quiz Master"}
                  {selectedMode === "roadmap" && "Roadmap Builder"}
                  {selectedMode === "doubt" && "Doubt Solver"}
                  {selectedMode === "strategy" && "Exam Strategy"}
                </span>
              </p>
            </div>

            {/* FINAL PREMIUM INPUT BAR — MIC + AUTO-SPEAK + SEND */}
            <div className="flex items-center gap-4 px-1">

              {/* AUTO-SPEAK TOGGLE */}
              <button
                onClick={() => setAutoSpeak(!autoSpeak)}
                className={`p-3 rounded-xl transition-all transform hover:scale-110 ${
                  autoSpeak
                    ? 'bg-gradient-to-r from-purple-600 to-pink-600 shadow-lg shadow-purple-500/30'
                    : 'bg-white/10 hover:bg-white/20'
                }`}
                title={autoSpeak ? "Auto-speak ON" : "Auto-speak OFF"}
              >
                {autoSpeak ? (
                  <Volume2 className="w-6 h-6 text-white" />
                ) : (
                  <VolumeX className="w-6 h-6 text-gray-400" />
                )}
              </button>

              {/* TEXT INPUT WITH MIC INSIDE */}
              <div className="flex-1 relative">
                <input
                  type="text"
                  value={userMsg}
                  onChange={(e) => setUserMsg(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
                  placeholder={`Ask in ${modeLabels[selectedMode]} mode...`}
                  className="w-full bg-white/10 backdrop-blur-xl border border-white/20 rounded-xl px-5 py-4 pr-16 text-white placeholder-gray-400 focus:outline-none focus:border-purple-400 transition"
                />

                {/* MIC BUTTON INSIDE INPUT */}
                <button
                  onClick={isListening ? stopListening : startListening}
                  className={`absolute right-3 top-1/2 -translate-y-1/2 p-3 rounded-lg transition-all ${
                    isListening
                      ? 'bg-red-500/30 animate-pulse'
                      : 'bg-white/20 hover:bg-white/30'
                  }`}
                >
                  {isListening ? (
                    <div className="relative">
                      <div className="absolute inset-0 bg-red-400 rounded-full animate-ping opacity-75"></div>
                      <Mic className="w-5 h-5 text-red-300 relative z-10" />
                    </div>
                  ) : (
                    <Mic className="w-5 h-5 text-purple-300" />
                  )}
                </button>
              </div>

              {/* SEND BUTTON */}
              <button
                onClick={sendMessage}
                disabled={(!userMsg.trim() && !transcript) || asking}
                className={`p-4 rounded-xl transition-all transform hover:scale-105 ${
                  (!userMsg.trim() && !transcript) || asking
                    ? 'bg-white/10 cursor-not-allowed'
                    : 'bg-gradient-to-r from-purple-600 to-pink-600 shadow-lg hover:from-purple-500 hover:to-pink-500'
                }`}
              >
                {asking ? (
                  <div className="w-6 h-6 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <Send className="w-6 h-6 text-white" />
                )}
              </button>
            </div>

            {/* LIVE TRANSCRIPTION */}
            {isListening && (
              <div className="mt-3 p-4 bg-white/5 backdrop-blur-xl rounded-xl border border-purple-500/30 text-center animate-pulse">
                <p className="text-purple-300 text-sm">Listening...</p>
                <p className="text-white text-lg font-medium mt-1">{transcript || "Speak now..."}</p>
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
}
import React, { useEffect, useState, useRef } from 'react';

const VOICE_OPTIONS = [
  { value: 'male', label: '♂ Male (American)' },
  { value: 'female', label: '♀ Female (American)' },
  { value: 'indian', label: '♀ Indian Accent' },
];

const LANG_OPTIONS = [
  { value: 'auto', label: '🌐 Auto' },
  { value: 'en-IN', label: 'English' },
  { value: 'ta-IN', label: 'தமிழ்' },
  { value: 'hi-IN', label: 'हिन्दी' },
];

const SpeechToText = ({ onResult, selectedVoice, onVoiceChange, selectedLang, onLangChange }) => {
  const [isRecognizing, setIsRecognizing] = useState(false);
  const [textInput, setTextInput] = useState('');
  const recognitionRef = useRef(null);
  const isListeningRef = useRef(false);
  const micBtnRef = useRef(null);

  // Initialise speech recognition once
  useEffect(() => {
    if (!('SpeechRecognition' in window) && !('webkitSpeechRecognition' in window)) {
      console.warn('Speech recognition not supported in this browser.');
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recog = new SR();
    recog.continuous = false;
    recog.interimResults = false;
    recog.lang = selectedLang === 'auto' ? 'en-IN' : selectedLang;

    recog.onresult = (event) => {
      const speechTranscript = event.results[0][0].transcript;
      console.log('Transcript:', speechTranscript);
      if (onResult) onResult(speechTranscript);
    };

    recog.onend = () => {
      console.log('Speech recognition stopped');
      isListeningRef.current = false;
      setIsRecognizing(false);
    };

    recog.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      isListeningRef.current = false;
      setIsRecognizing(false);
    };

    recog.onabort = () => {
      console.log('Speech recognition aborted');
      isListeningRef.current = false;
      setIsRecognizing(false);
    };

    recognitionRef.current = recog;
  }, [onResult]);

  // ── START / STOP helpers ──────────────────────────────────
  const startRecognition = () => {
    if (!recognitionRef.current || isListeningRef.current) return;
    isListeningRef.current = true;
    setIsRecognizing(true);
    console.log('Speech recognition starting...');
    try {
      recognitionRef.current.start();
    } catch (err) {
      console.error('Error starting speech recognition:', err);
      isListeningRef.current = false;
      setIsRecognizing(false);
    }
  };

  const stopRecognition = () => {
    if (!recognitionRef.current || !isListeningRef.current) return;
    try {
      recognitionRef.current.stop();
    } catch (err) {
      console.warn('Error stopping speech recognition:', err);
    }
    isListeningRef.current = false;
    setIsRecognizing(false);
    console.log('Speech recognition stopped manually');
  };

  const handleTextSubmit = (e) => {
    e.preventDefault();
    if (!textInput.trim()) return;
    if (onResult) onResult(textInput.trim());
    setTextInput('');
  };

  // ── Hold-T keyboard shortcut ──────────────────────────────
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if ((e.key === 'T' || e.key === 't') && !e.repeat && !isListeningRef.current) {
        startRecognition();
      }
    };
    const handleKeyUp = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if ((e.key === 'T' || e.key === 't') && isListeningRef.current) {
        stopRecognition();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  // ── Touch events with { passive: false } to allow preventDefault ──
  useEffect(() => {
    const btn = micBtnRef.current;
    if (!btn) return;
    const onTouchStart = (e) => { e.preventDefault(); startRecognition(); };
    const onTouchEnd   = (e) => { e.preventDefault(); stopRecognition(); };
    btn.addEventListener('touchstart', onTouchStart, { passive: false });
    btn.addEventListener('touchend',   onTouchEnd,   { passive: false });
    return () => {
      btn.removeEventListener('touchstart', onTouchStart);
      btn.removeEventListener('touchend',   onTouchEnd);
    };
  }, []);

  // ── UI ────────────────────────────────────────────────────
  return (
    <div className="speech-controls">

      {/* Selectors Wrapper */}
      <div style={{ marginBottom: '10px', display: 'flex', gap: '16px', alignItems: 'center' }}>
        {/* Language Selector */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#aaa', fontSize: '13px' }}>Language:</span>
          <select
            value={selectedLang}
            onChange={(e) => onLangChange(e.target.value)}
            style={{
              background: 'rgba(255, 255, 255, 0.1)',
              color: '#fff',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: '8px',
              padding: '4px 10px',
              fontSize: '13px',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {LANG_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} style={{ background: '#222', color: '#fff' }}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Voice Selector */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#aaa', fontSize: '13px' }}>Voice:</span>
          <select
            value={selectedVoice}
            onChange={(e) => onVoiceChange(e.target.value)}
            style={{
              background: 'rgba(255, 255, 255, 0.1)',
              color: '#fff',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: '8px',
              padding: '4px 10px',
              fontSize: '13px',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            {VOICE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} style={{ background: '#222', color: '#fff' }}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Text Input Form */}
      <form onSubmit={handleTextSubmit} style={{ display: 'flex', gap: '8px', width: '100%', marginBottom: '10px' }}>
        <input
          type="text"
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          placeholder="Type your message here..."
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: '20px',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            background: 'rgba(0, 0, 0, 0.5)',
            color: '#fff',
            fontSize: '14px',
            outline: 'none',
          }}
        />
        <button
          type="submit"
          style={{
            padding: '10px 18px',
            borderRadius: '20px',
            border: 'none',
            background: '#6366f1',
            color: '#fff',
            fontWeight: '600',
            cursor: 'pointer',
            fontSize: '14px',
          }}
        >
          Send
        </button>
      </form>

      {/* Mic button — hold to talk */}
      <button
        ref={micBtnRef}
        className={`mic-btn ${isRecognizing ? 'mic-btn--active' : ''}`}
        onMouseDown={startRecognition}
        onMouseUp={stopRecognition}
        title="Hold to speak (or hold T)"
      >
        {isRecognizing ? (
          <>
            <span className="mic-icon">🔴</span>
            <span>Listening…</span>
          </>
        ) : (
          <>
            <span className="mic-icon">🎙️</span>
            <span>Hold to Talk</span>
          </>
        )}
      </button>

      <p className="mic-hint">or hold <kbd>T</kbd> to speak</p>
    </div>
  );
};

export default SpeechToText;
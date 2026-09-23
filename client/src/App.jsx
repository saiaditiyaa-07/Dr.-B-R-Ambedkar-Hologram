import React, { useState, useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { Environment } from '@react-three/drei';
import './app.css';
import SpeechToText from './components/SpeechToText.jsx';
import Exp from './components/Exp.jsx';
import Player_lipsync_2D from './components/Player_lipsync_2D.jsx';

function App() {
  const [transcript, setTranscript] = useState('');
  const [replyText, setReplyText] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isIdle, setIsIdle] = useState(true);
  const [lipsyncData, setLipsyncData] = useState(null);
  const [audioProgress, setAudioProgress] = useState(0);
  const [selectedVoice, setSelectedVoice] = useState('male');
  const [selectedLang, setSelectedLang] = useState('auto');
  const [isLoading, setIsLoading] = useState(false);

  // Reference to the <audio> element in the DOM
  const audioRef = useRef(null);
  const progressTimerRef = useRef(null);

  // Stop any currently playing audio and clear timers
  const stopCurrentAudio = () => {
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
  };

  // Play audio using the DOM <audio> element
  const playAudio = async (url, mouthCues) => {
    try {
      const bustedUrl = url.includes('?') ? `${url}&t=${Date.now()}` : `${url}?t=${Date.now()}`;
      const ext = url.split('?')[0].split('.').pop().toLowerCase();
      const mimeType = ext === 'mp3' ? 'audio/mpeg' : (ext === 'wav' ? 'audio/wav' : 'audio/unknown');

      console.log(`[Audio] URL: ${bustedUrl}`);
      console.log(`[Audio] MIME/type: ${mimeType}`);

      stopCurrentAudio();

      const audio = audioRef.current;
      if (!audio) return;

      audio.src = bustedUrl;
      audio.load();

      // Track playback progress for lipsync
      const updateProgress = () => {
        setAudioProgress(audio.currentTime);
      };
      
      const onEnded = () => {
        audio.removeEventListener('timeupdate', updateProgress);
        audio.removeEventListener('ended', onEnded);
        setIsSpeaking(false);
        setIsIdle(true);
        setAudioProgress(0);
        setLipsyncData(null);
      };

      const onError = (e) => {
        console.error(`[Audio] Playback error:`, audio.error || e);
      };

      audio.addEventListener('timeupdate', updateProgress);
      audio.addEventListener('ended', onEnded);
      audio.addEventListener('error', onError, { once: true });

      // Play the audio
      await audio.play();
      console.log(`[Audio] Playback started`);

    } catch (err) {
      console.error(`[Audio] Playback error:`, err);
      simulateSpeechAnimation(mouthCues);
    }
  };

  // Fallback: animate avatar with a timer when audio can't play
  const simulateSpeechAnimation = (mouthCues) => {
    const totalDuration = (mouthCues && mouthCues.length > 0)
      ? mouthCues[mouthCues.length - 1].end
      : 4.0;
    const startTime = Date.now();

    if (progressTimerRef.current) clearInterval(progressTimerRef.current);
    progressTimerRef.current = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000;
      setAudioProgress(elapsed);
      if (elapsed >= totalDuration) {
        clearInterval(progressTimerRef.current);
        progressTimerRef.current = null;
        setIsSpeaking(false);
        setIsIdle(true);
        setAudioProgress(0);
        setLipsyncData(null);
      }
    }, 30);
  };

  const handleSpeechResult = async (speechTranscript) => {
    setTranscript(speechTranscript);
    setIsLoading(true);
    setReplyText('');
    console.log('Recognized text:', speechTranscript);

    stopCurrentAudio();

    // Trigger a dummy play right now in the sync gesture window to unlock audio
    if (audioRef.current) {
      audioRef.current.play().then(() => audioRef.current.pause()).catch(() => {});
    }

    try {
      const response = await fetch('http://127.0.0.1:8001/voice-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: speechTranscript, voice: selectedVoice, input_lang: selectedLang }),
      });

      setIsLoading(false);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();
      console.log('Voice chat response:', data);

      const { audio_url, mouthCues, text } = data;
      setReplyText(text || '');
      setLipsyncData(mouthCues);
      setIsSpeaking(true);
      setIsIdle(false);

      if (!audio_url) {
        console.warn('No audio URL — running silent lipsync animation');
        simulateSpeechAnimation(mouthCues);
        return;
      }

      await playAudio(audio_url, mouthCues);

    } catch (error) {
      setIsLoading(false);
      console.error('Pipeline error:', error);
      setReplyText('Sorry, something went wrong. Please try again!');
      setIsSpeaking(false);
      setIsIdle(true);
    }
  };

  const stopSpeaking = () => {
    stopCurrentAudio();
    setIsSpeaking(false);
    setIsIdle(true);
    setAudioProgress(0);
    setLipsyncData(null);
  };

  // Space bar stops speaking
  useEffect(() => {
    const handleKeyPress = (event) => {
      if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') return;
      if (event.code === 'Space') stopSpeaking();
    };
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  const [displayMode, setDisplayMode] = useState('laptop'); // 'laptop' | 'hologram'

  return (
    <div className={`container ${displayMode === 'laptop' ? 'laptop-mode' : 'hologram-mode'}`}>
      
      {/* Hidden DOM Audio Element for reliable playback */}
      <audio ref={audioRef} style={{ display: 'none' }} />

      {/* Mode Switcher Toggle Button */}
      <div className="mode-toggle-container">
        <button
          className="mode-toggle-btn"
          onClick={() => setDisplayMode(prev => prev === 'laptop' ? 'hologram' : 'laptop')}
          title="Toggle display mode for Laptop vs Glass Hologram setup"
        >
          {displayMode === 'laptop' ? '💻 Laptop Mode' : '📐 Hologram Mode'}
        </button>
      </div>

      <Canvas className="canvas">
        <ambientLight intensity={0.5} />
        <Environment preset="sunset" />
        <Exp
          isSpeaking={isSpeaking}
          isIdle={isIdle}
          lipsyncData={lipsyncData}
          audioProgress={audioProgress}
        />
      </Canvas>

      {/* Compact Floating Response Text Panel */}
      {(replyText || isLoading) && (
        <div className="response-panel">
          <div className="response-panel-header">
            <span className="avatar-icon">🏛️</span>
            <span className="avatar-name">Dr. B. R. Ambedkar</span>
          </div>
          <div className="response-panel-body">
            {isLoading ? (
              <div className="loading-state">
                <span className="pulse-dot"></span>
                <span>Thinking &amp; generating voice... 💭</span>
              </div>
            ) : (
              <span>{replyText}</span>
            )}
          </div>
        </div>
      )}

      {/* Voice selector + speech/text input */}
      <SpeechToText
        onResult={handleSpeechResult}
        selectedVoice={selectedVoice}
        onVoiceChange={setSelectedVoice}
        selectedLang={selectedLang}
        onLangChange={setSelectedLang}
      />
    </div>
  );
}

export default App;
import React, { useState, useEffect } from 'react';

const corresponding = {
  A: "PP",
  B: "kk",
  C: "I",
  D: "AA",
  E: "O",
  F: "U",
  G: "FF",
  H: "TH",
  X: "PP",
};

export default function Player_lipsync_2D({ isSpeaking, isIdle, audioProgress = 0, lipsyncData = [] }) {
  const [currentViseme, setCurrentViseme] = useState('idle');
  const [gestureClass, setGestureClass] = useState('gesture-idle');

  // Body animations (Idle vs Talking)
  useEffect(() => {
    let intervalId = null;

    if (isIdle) {
      setGestureClass('gesture-idle');
    } else if (isSpeaking) {
      setGestureClass('gesture-talking-1');
      intervalId = setInterval(() => {
        setGestureClass((prev) => {
          return prev === 'gesture-talking-1' ? 'gesture-talking-2' : 'gesture-talking-1';
        });
      }, 3500);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isIdle, isSpeaking]);

  // Real-time mouth lipsync based on audioProgress and lipsyncData
  useEffect(() => {
    if (!isSpeaking || !lipsyncData || lipsyncData.length === 0) {
      setCurrentViseme('idle');
      return;
    }

    // Find current active mouth cue based on elapsed audioProgress
    const currentCue = lipsyncData.find(
      (cue) => audioProgress >= cue.start && audioProgress <= cue.end
    );

    if (currentCue && corresponding[currentCue.value]) {
      setCurrentViseme(corresponding[currentCue.value]);
    } else {
      setCurrentViseme('idle');
    }
  }, [isSpeaking, audioProgress, lipsyncData]);

  return (
    <div className={`puppet-container ${isSpeaking ? 'is-speaking' : 'is-idle'} ${gestureClass}`}>
      {/* 
        NOTE: These image paths expect you to manually slice the Ambedkar avatar and place 
        them in client/public/assets/. 
        The mouth layer uses dynamic viseme states matching the Rhubarb audio data! 
      */}
      <img src="/assets/torso.png" className="puppet-layer puppet-torso" alt="torso" />
      <img src="/assets/left_arm.png" className="puppet-layer puppet-left-arm" alt="left arm" />
      <img src="/assets/right_arm.png" className="puppet-layer puppet-right-arm" alt="right arm" />
      <img src="/assets/head.png" className="puppet-layer puppet-head" alt="head" />
      <img src={`/assets/mouth_${currentViseme}.png`} className="puppet-layer puppet-mouth" alt="mouth" />
    </div>
  );
}

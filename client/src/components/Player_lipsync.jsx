import React, { useRef, useEffect, useState } from 'react';
import { useGraph } from '@react-three/fiber';
import { useGLTF, useAnimations } from '@react-three/drei';
import { SkeletonUtils } from 'three-stdlib';
import * as THREE from 'three';

const corresponding = {
  A: "viseme_PP",
  B: "viseme_kk",
  C: "viseme_I",
  D: "viseme_AA",
  E: "viseme_O",
  F: "viseme_U",
  G: "viseme_FF",
  H: "viseme_TH",
  X: "viseme_PP",
};

export default function Player_lipsync({ isSpeaking, isIdle, audioProgress = 0, lipsyncData = [] }) {
  const group = useRef();
  const { scene } = useGLTF('/models/player_lipsync.glb');
  const { animations } = useGLTF('/models/animations.glb');
  const clone = React.useMemo(() => SkeletonUtils.clone(scene), [scene]);
  const { nodes, materials } = useGraph(clone);
  const { actions, names } = useAnimations(animations, group);
  const [talkingIndex, setTalkingIndex] = useState(1);
  const activeAnimationRef = useRef(null);

  const playAnimation = (index) => {
    if (!names || !names[index] || !actions[names[index]]) return;
    const nextAction = actions[names[index]];
    if (activeAnimationRef.current && activeAnimationRef.current !== nextAction) {
      activeAnimationRef.current.fadeOut(0.3);
    }
    nextAction.reset().fadeIn(0.3).play();
    activeAnimationRef.current = nextAction;
  };

  // Body animations (Idle vs Talking)
  useEffect(() => {
    let intervalId = null;

    if (isIdle) {
      playAnimation(0); // Idle animation
      // Reset mouth morphs when idle
      Object.values(corresponding).forEach((viseme) => {
        if (nodes.Wolf3D_Head?.morphTargetDictionary?.[viseme] !== undefined) {
          nodes.Wolf3D_Head.morphTargetInfluences[nodes.Wolf3D_Head.morphTargetDictionary[viseme]] = 0;
        }
        if (nodes.Wolf3D_Teeth?.morphTargetDictionary?.[viseme] !== undefined) {
          nodes.Wolf3D_Teeth.morphTargetInfluences[nodes.Wolf3D_Teeth.morphTargetDictionary[viseme]] = 0;
        }
      });
    } else if (isSpeaking) {
      playAnimation(talkingIndex);
      intervalId = setInterval(() => {
        setTalkingIndex((prev) => {
          const next = prev === 1 ? 2 : 1;
          playAnimation(next);
          return next;
        });
      }, 3500);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isIdle, isSpeaking, names, actions]);

  // Real-time mouth lipsync based on audioProgress and lipsyncData
  useEffect(() => {
    if (!isSpeaking || !lipsyncData || lipsyncData.length === 0) {
      // Reset mouth target influences
      Object.values(corresponding).forEach((viseme) => {
        if (nodes.Wolf3D_Head?.morphTargetDictionary?.[viseme] !== undefined) {
          nodes.Wolf3D_Head.morphTargetInfluences[nodes.Wolf3D_Head.morphTargetDictionary[viseme]] = 0;
        }
        if (nodes.Wolf3D_Teeth?.morphTargetDictionary?.[viseme] !== undefined) {
          nodes.Wolf3D_Teeth.morphTargetInfluences[nodes.Wolf3D_Teeth.morphTargetDictionary[viseme]] = 0;
        }
      });
      return;
    }

    // Find current active mouth cue based on elapsed audioProgress
    const currentCue = lipsyncData.find(
      (cue) => audioProgress >= cue.start && audioProgress <= cue.end
    );

    // Reset all mouth shapes
    Object.values(corresponding).forEach((viseme) => {
      if (nodes.Wolf3D_Head?.morphTargetDictionary?.[viseme] !== undefined) {
        nodes.Wolf3D_Head.morphTargetInfluences[nodes.Wolf3D_Head.morphTargetDictionary[viseme]] = 0;
      }
      if (nodes.Wolf3D_Teeth?.morphTargetDictionary?.[viseme] !== undefined) {
        nodes.Wolf3D_Teeth.morphTargetInfluences[nodes.Wolf3D_Teeth.morphTargetDictionary[viseme]] = 0;
      }
    });

    if (currentCue && corresponding[currentCue.value]) {
      const activeViseme = corresponding[currentCue.value];
      if (nodes.Wolf3D_Head?.morphTargetDictionary?.[activeViseme] !== undefined) {
        nodes.Wolf3D_Head.morphTargetInfluences[nodes.Wolf3D_Head.morphTargetDictionary[activeViseme]] = 1;
      }
      if (nodes.Wolf3D_Teeth?.morphTargetDictionary?.[activeViseme] !== undefined) {
        nodes.Wolf3D_Teeth.morphTargetInfluences[nodes.Wolf3D_Teeth.morphTargetDictionary[activeViseme]] = 1;
      }
    }
  }, [isSpeaking, audioProgress, lipsyncData, nodes]);

  return (
    <group ref={group} dispose={null} position={[0, -4.5, -1]} scale={[4, 4, 4]} rotation={[0, 0, 0]}>
      <primitive object={nodes.Hips} />
      <skinnedMesh geometry={nodes.Wolf3D_Hair.geometry} material={materials.Wolf3D_Hair} skeleton={nodes.Wolf3D_Hair.skeleton} />
      <skinnedMesh geometry={nodes.Wolf3D_Body.geometry} material={materials.Wolf3D_Body} skeleton={nodes.Wolf3D_Body.skeleton} />
      <skinnedMesh geometry={nodes.Wolf3D_Outfit_Bottom.geometry} material={materials.Wolf3D_Outfit_Bottom} skeleton={nodes.Wolf3D_Outfit_Bottom.skeleton} />
      <skinnedMesh geometry={nodes.Wolf3D_Outfit_Footwear.geometry} material={materials.Wolf3D_Outfit_Footwear} skeleton={nodes.Wolf3D_Outfit_Footwear.skeleton} />
      <skinnedMesh geometry={nodes.Wolf3D_Outfit_Top.geometry} material={materials.Wolf3D_Outfit_Top} skeleton={nodes.Wolf3D_Outfit_Top.skeleton} />
      <skinnedMesh name="EyeLeft" geometry={nodes.EyeLeft.geometry} material={materials.Wolf3D_Eye} skeleton={nodes.EyeLeft.skeleton} morphTargetDictionary={nodes.EyeLeft.morphTargetDictionary} morphTargetInfluences={nodes.EyeLeft.morphTargetInfluences} />
      <skinnedMesh name="EyeRight" geometry={nodes.EyeRight.geometry} material={materials.Wolf3D_Eye} skeleton={nodes.EyeRight.skeleton} morphTargetDictionary={nodes.EyeRight.morphTargetDictionary} morphTargetInfluences={nodes.EyeRight.morphTargetInfluences} />
      <skinnedMesh name="Wolf3D_Head" geometry={nodes.Wolf3D_Head.geometry} material={materials.Wolf3D_Skin} skeleton={nodes.Wolf3D_Head.skeleton} morphTargetDictionary={nodes.Wolf3D_Head.morphTargetDictionary} morphTargetInfluences={nodes.Wolf3D_Head.morphTargetInfluences} />
      <skinnedMesh name="Wolf3D_Teeth" geometry={nodes.Wolf3D_Teeth.geometry} material={materials.Wolf3D_Teeth} skeleton={nodes.Wolf3D_Teeth.skeleton} morphTargetDictionary={nodes.Wolf3D_Teeth.morphTargetDictionary} morphTargetInfluences={nodes.Wolf3D_Teeth.morphTargetInfluences} />
    </group>
  );
}

useGLTF.preload('/models/player_lipsync.glb');

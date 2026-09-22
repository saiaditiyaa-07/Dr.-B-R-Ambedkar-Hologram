import React from 'react'
import Player_lipsync from './Player_lipsync.jsx'

function Exp({isSpeaking,isIdle,lipsyncData,audioProgress}) {
  return (
    <>
      <Player_lipsync isSpeaking={isSpeaking} isIdle={isIdle} lipsyncData={lipsyncData} audioProgress={audioProgress}/>
       
        </>
      
  )
}

export default Exp;
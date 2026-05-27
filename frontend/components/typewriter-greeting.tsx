'use client';

import React, { useState, useEffect } from 'react';

const phrases = [
  "How can I guide your engineering admission today?",
  "Let's find the best college for your Assam CEE rank.",
  "Need help with JEE Mains counseling policies?",
  "Ask me about cutoffs, colleges, or admission steps."
];

export function TypewriterGreeting() {
  const [text, setText] = useState('');
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);
  const [typingSpeed, setTypingSpeed] = useState(80);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    const currentPhrase = phrases[phraseIndex];

    if (!isDeleting && text === currentPhrase) {
      // Pause at the end of typing
      timer = setTimeout(() => setIsDeleting(true), 2500);
    } else if (isDeleting && text === '') {
      // Move to next phrase
      timer = setTimeout(() => {
        setIsDeleting(false);
        setPhraseIndex((prev) => (prev + 1) % phrases.length);
        setTypingSpeed(80);
      }, 100);
    } else {
      // Typing or deleting
      timer = setTimeout(() => {
        setText(currentPhrase.substring(0, text.length + (isDeleting ? -1 : 1)));
        // Speed up slightly when deleting
        setTypingSpeed(isDeleting ? 40 : 80);
      }, typingSpeed);
    }

    return () => clearTimeout(timer);
  }, [text, isDeleting, phraseIndex, typingSpeed]);

  return (
    <span>
      {text}
      <span className="inline-block w-[3px] h-[0.9em] bg-white translate-y-[2px] ml-[2px] animate-pulse"></span>
    </span>
  );
}

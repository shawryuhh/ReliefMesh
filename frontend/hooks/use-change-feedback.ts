"use client";
import { useEffect, useRef, useState } from "react";
export function useChangeFeedback(value: unknown) {
  const previous = useRef(value); const [changed,setChanged] = useState(false);
  useEffect(() => { const before = previous.current; previous.current = value; if (before === undefined || before === value) return; setChanged(true); const timer = setTimeout(() => setChanged(false),650); return () => clearTimeout(timer); },[value]);
  return changed;
}

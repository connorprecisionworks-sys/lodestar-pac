import { useEffect, useState } from "react";

export default function SplashScreen({ onDone }) {
  const [out, setOut] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => setOut(true), 2800);
    const t2 = setTimeout(onDone, 3400);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [onDone]);

  const skip = () => { setOut(true); setTimeout(onDone, 500); };

  return (
    <div className={"splash" + (out ? " out" : "")} onClick={skip}>
      <img className="splash-star" src="/brand/star-glitch.gif" alt="" />
      <img className="splash-word" src="/brand/wordmark.png" alt="Lodestar PAC" />
      <div className="splash-enter">click to enter</div>
    </div>
  );
}

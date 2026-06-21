import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { EARTH, PLANETS, orbitPoints, positionAtMeanAnomaly, transferArc } from "../lib/orbits.js";

const SCALE = 4; // scene units per AU

function orbitLine(el, color, opacity = 0.6) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(orbitPoints(el).map((v) => v * SCALE), 3));
  return new THREE.LineLoop(g, new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
}

export default function OrbitViewer({ detail, trajectory }) {
  const mountRef = useRef(null);
  const tplusRef = useRef(null);
  const refs = useRef({});

  useEffect(() => {
    const mount = mountRef.current;
    const width = mount.clientWidth;
    const height = mount.clientHeight || 460;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x08090b);
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 2000);
    camera.position.set(0, -13, 9);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    const sun = new THREE.Mesh(new THREE.SphereGeometry(0.3, 24, 24),
      new THREE.MeshBasicMaterial({ color: 0xffcf5e }));
    scene.add(sun);
    scene.add(new THREE.PointLight(0xffffff, 1.6, 0));
    scene.add(new THREE.AmbientLight(0x3a3f47, 1.4));

    const grid = new THREE.GridHelper(28, 28, 0x151820, 0x0f1116);
    grid.rotation.x = Math.PI / 2;
    scene.add(grid);

    // asteroid belt: a faint scatter between ~2.1 and 3.3 AU
    const N = 900;
    const belt = new Float32Array(N * 3);
    for (let k = 0; k < N; k++) {
      const r = (2.1 + Math.random() * 1.2) * SCALE;
      const th = Math.random() * Math.PI * 2;
      belt[k * 3] = r * Math.cos(th);
      belt[k * 3 + 1] = r * Math.sin(th);
      belt[k * 3 + 2] = (Math.random() - 0.5) * 0.6 * SCALE;
    }
    const beltGeo = new THREE.BufferGeometry();
    beltGeo.setAttribute("position", new THREE.BufferAttribute(belt, 3));
    scene.add(new THREE.Points(beltGeo, new THREE.PointsMaterial({
      color: 0x4a5158, size: 0.05, transparent: true, opacity: 0.5,
    })));

    // planets: orbit lines + animated markers
    const planetMarkers = [];
    for (const p of PLANETS) {
      scene.add(orbitLine(p, p.color, 0.35));
      const m = new THREE.Mesh(new THREE.SphereGeometry(p.name === "Earth" ? 0.14 : 0.11, 16, 16),
        new THREE.MeshStandardMaterial({ color: p.color, emissive: p.color, emissiveIntensity: 0.25 }));
      scene.add(m);
      planetMarkers.push({ el: p, mesh: m });
    }

    Object.assign(refs.current, {
      scene, camera, renderer, controls, planetMarkers,
      asteroidOrbit: null, asteroidMarker: null, transferLine: null,
      craft: null, trail: null, flightPath: null, flightDays: 0, prog: 0, t: 0,
    });

    let raf;
    const animate = () => {
      const R = refs.current;
      R.t += 0.6;
      for (const { el, mesh } of R.planetMarkers) {
        const rate = 365.25 / el.period_days;
        const pos = positionAtMeanAnomaly(el, el.ma_deg + R.t * rate);
        mesh.position.set(pos[0] * SCALE, pos[1] * SCALE, pos[2] * SCALE);
      }
      if (R.asteroidEl && R.asteroidMarker) {
        const rate = R.asteroidEl.per_days ? 365.25 / R.asteroidEl.per_days : 1;
        const ap = positionAtMeanAnomaly(R.asteroidEl, (R.asteroidEl.ma_deg || 0) + R.t * rate);
        R.asteroidMarker.position.set(ap[0] * SCALE, ap[1] * SCALE, ap[2] * SCALE);
      }
      // mission flythrough
      if (R.flightPath && R.craft) {
        R.prog += 0.0035;
        if (R.prog > 1) R.prog = 0;
        const n = R.flightPath.length;
        const idx = Math.min(n - 1, Math.floor(R.prog * (n - 1)));
        const p = R.flightPath[idx];
        R.craft.position.set(p[0], p[1], p[2]);
        R.trail.geometry.setDrawRange(0, idx + 1);
        if (tplusRef.current) tplusRef.current.textContent = `T+ ${Math.round(R.prog * R.flightDays)} d`;
      }
      R.controls.update();
      R.renderer.render(R.scene, R.camera);
      raf = requestAnimationFrame(animate);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth, h = mount.clientHeight || 460;
      camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
      refs.current = {};
    };
  }, []);

  // selected asteroid orbit
  useEffect(() => {
    const R = refs.current;
    if (!R.scene) return;
    for (const key of ["asteroidOrbit", "asteroidMarker"]) {
      if (R[key]) { R.scene.remove(R[key]); R[key] = null; }
    }
    R.asteroidEl = null;
    if (!detail || detail.a_au == null) return;
    const el = {
      a_au: detail.a_au, e: detail.e, i_deg: detail.i_deg, om_deg: detail.om_deg,
      w_deg: detail.w_deg, ma_deg: detail.ma_deg, per_days: detail.per_days,
    };
    R.asteroidEl = el;
    R.asteroidOrbit = orbitLine(el, 0xeaeaea, 0.95);
    R.scene.add(R.asteroidOrbit);
    R.asteroidMarker = new THREE.Mesh(new THREE.SphereGeometry(0.14, 16, 16),
      new THREE.MeshStandardMaterial({ color: 0xeaeaea, emissive: 0x232326 }));
    R.scene.add(R.asteroidMarker);
  }, [detail]);

  // transfer arc + flythrough setup
  useEffect(() => {
    const R = refs.current;
    if (!R.scene) return;
    for (const key of ["transferLine", "craft", "trail"]) {
      if (R[key]) { R.scene.remove(R[key]); R[key] = null; }
    }
    R.flightPath = null;
    if (tplusRef.current) tplusRef.current.textContent = "";
    if (!trajectory || !R.asteroidEl) return;

    if (trajectory.transferPath) {
      const p = trajectory.transferPath;
      const scaled = p.map((pt) => [pt[0] * SCALE, pt[1] * SCALE, pt[2] * SCALE]);
      const flat = new Float32Array(scaled.length * 3);
      scaled.forEach((pt, i) => { flat[i * 3] = pt[0]; flat[i * 3 + 1] = pt[1]; flat[i * 3 + 2] = pt[2]; });
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(flat, 3));
      R.transferLine = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x6a7280 }));
      R.scene.add(R.transferLine);

      // growing trail + craft for the flythrough
      const tg = new THREE.BufferGeometry();
      tg.setAttribute("position", new THREE.BufferAttribute(flat.slice(), 3));
      tg.setDrawRange(0, 1);
      R.trail = new THREE.Line(tg, new THREE.LineBasicMaterial({ color: 0xf0f4ff }));
      R.scene.add(R.trail);
      R.craft = new THREE.Mesh(new THREE.SphereGeometry(0.1, 12, 12),
        new THREE.MeshBasicMaterial({ color: 0xffffff }));
      R.scene.add(R.craft);
      R.flightPath = scaled;
      R.flightDays = trajectory.optimal ? trajectory.optimal.tofDays : 0;
      R.prog = 0;
      return;
    }

    // schematic fallback (no epoch / screening mode)
    const ep = positionAtMeanAnomaly(EARTH, EARTH.ma_deg + R.t);
    const ap = positionAtMeanAnomaly(R.asteroidEl, (R.asteroidEl.ma_deg || 0) + R.t);
    const pts = transferArc(ep, ap);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pts.map((v) => v * SCALE), 3));
    const line = new THREE.Line(g, new THREE.LineDashedMaterial({ color: 0xeaeaea, dashSize: 0.4, gapSize: 0.25 }));
    line.computeLineDistances();
    R.transferLine = line;
    R.scene.add(line);
  }, [trajectory]);

  return (
    <div className="orbit-wrap">
      <div ref={mountRef} className="orbit-canvas">
        <span className="orbit-corner tl">Heliocentric Frame · Ecliptic</span>
        <span className="orbit-corner tr" ref={tplusRef}></span>
        <span className="orbit-corner bl">Drag to orbit · Scroll to zoom</span>
      </div>
      <div className="orbit-legend">
        <span><i style={{ background: "#ffcf5e" }} />Sun</span>
        <span><i style={{ background: "#6f9cff" }} />Earth</span>
        <span><i style={{ background: "#d1593f" }} />Planets</span>
        <span><i style={{ background: "#eaeaea" }} />Target</span>
        {trajectory?.transferPath && <span><i style={{ background: "#f0f4ff" }} />Transfer + craft</span>}
      </div>
    </div>
  );
}

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { EARTH, orbitPoints, positionAtMeanAnomaly, transferArc } from "../lib/orbits.js";

const SCALE = 4; // scene units per AU

function lineFromPoints(arr, color, opacity = 1) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(arr.map((v) => v * SCALE), 3));
  const m = new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity });
  return new THREE.LineLoop(g, m);
}

export default function OrbitViewer({ detail, trajectory }) {
  const mountRef = useRef(null);
  const refs = useRef({});

  // one-time scene setup
  useEffect(() => {
    const mount = mountRef.current;
    const width = mount.clientWidth;
    const height = mount.clientHeight || 460;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0e17);
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000);
    camera.position.set(0, -9, 7);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;

    // Sun
    const sun = new THREE.Mesh(
      new THREE.SphereGeometry(0.35, 24, 24),
      new THREE.MeshBasicMaterial({ color: 0xffd166 })
    );
    scene.add(sun);
    scene.add(new THREE.PointLight(0xffffff, 1.6, 0));
    scene.add(new THREE.AmbientLight(0x404a60, 1.2));

    // ecliptic reference grid
    const grid = new THREE.GridHelper(20, 20, 0x1c2740, 0x141c2c);
    grid.rotation.x = Math.PI / 2;
    scene.add(grid);

    // Earth orbit + marker
    const earthOrbit = lineFromPoints(orbitPoints(EARTH), 0x6f9cff, 0.7);
    scene.add(earthOrbit);
    const earthMarker = new THREE.Mesh(
      new THREE.SphereGeometry(0.16, 16, 16),
      new THREE.MeshStandardMaterial({ color: 0x6f9cff, emissive: 0x24407f })
    );
    scene.add(earthMarker);

    Object.assign(refs.current, {
      scene, camera, renderer, controls, earthMarker,
      asteroidOrbit: null, asteroidMarker: null, transferLine: null,
      t: 0,
    });

    let raf;
    const animate = () => {
      const R = refs.current;
      R.t += 0.6;
      // Earth marker
      const ep = positionAtMeanAnomaly(EARTH, EARTH.ma_deg + R.t);
      R.earthMarker.position.set(ep[0] * SCALE, ep[1] * SCALE, ep[2] * SCALE);
      // Asteroid marker
      if (R.asteroidEl && R.asteroidMarker) {
        const rate = R.asteroidEl.per_days ? (365.25 / R.asteroidEl.per_days) : 1;
        const ap = positionAtMeanAnomaly(R.asteroidEl, (R.asteroidEl.ma_deg || 0) + R.t * rate);
        R.asteroidMarker.position.set(ap[0] * SCALE, ap[1] * SCALE, ap[2] * SCALE);
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

  // rebuild asteroid orbit when the selected object changes
  useEffect(() => {
    const R = refs.current;
    if (!R.scene) return;
    for (const key of ["asteroidOrbit", "asteroidMarker"]) {
      if (R[key]) { R.scene.remove(R[key]); R[key] = null; }
    }
    R.asteroidEl = null;
    if (!detail || detail.a_au == null) return;

    const el = {
      a_au: detail.a_au, e: detail.e, i_deg: detail.i_deg,
      om_deg: detail.om_deg, w_deg: detail.w_deg, ma_deg: detail.ma_deg,
      per_days: detail.per_days,
    };
    R.asteroidEl = el;
    R.asteroidOrbit = lineFromPoints(orbitPoints(el), 0xe8634f, 0.9);
    R.scene.add(R.asteroidOrbit);
    R.asteroidMarker = new THREE.Mesh(
      new THREE.SphereGeometry(0.14, 16, 16),
      new THREE.MeshStandardMaterial({ color: 0xe8634f, emissive: 0x5a1c12 })
    );
    R.scene.add(R.asteroidMarker);
  }, [detail]);

  // draw / clear the schematic transfer arc when a trajectory is computed
  useEffect(() => {
    const R = refs.current;
    if (!R.scene) return;
    if (R.transferLine) { R.scene.remove(R.transferLine); R.transferLine = null; }
    if (!trajectory || !R.asteroidEl) return;

    const ep = positionAtMeanAnomaly(EARTH, EARTH.ma_deg + R.t);
    const ap = positionAtMeanAnomaly(R.asteroidEl, (R.asteroidEl.ma_deg || 0) + R.t);
    const pts = transferArc(ep, ap);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pts.map((v) => v * SCALE), 3));
    const m = new THREE.LineDashedMaterial({ color: 0x9b7cff, dashSize: 0.5, gapSize: 0.3 });
    const line = new THREE.Line(g, m);
    line.computeLineDistances();
    R.transferLine = line;
    R.scene.add(line);
  }, [trajectory]);

  return (
    <div className="orbit-wrap">
      <div ref={mountRef} className="orbit-canvas" />
      <div className="orbit-legend">
        <span><i style={{ background: "#ffd166" }} />Sun</span>
        <span><i style={{ background: "#6f9cff" }} />Earth</span>
        <span><i style={{ background: "#e8634f" }} />Selected asteroid</span>
        {trajectory && <span><i style={{ background: "#9b7cff" }} />Schematic transfer</span>}
      </div>
    </div>
  );
}

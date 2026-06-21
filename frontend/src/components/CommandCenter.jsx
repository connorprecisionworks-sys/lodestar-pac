import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { propagate, todayJd } from "../lib/astro.js";
import { EARTH, PLANETS, orbitPoints } from "../lib/orbits.js";
import { source } from "../api/source.js";

const SCALE = 4;
const COLOR = { C: [0.44, 0.45, 0.49], S: [0.70, 0.71, 0.74], M: [0.96, 0.96, 0.98] };

export default function CommandCenter({ selectedId, onSelect }) {
  const mountRef = useRef(null);
  const refs = useRef({});
  const [count, setCount] = useState(0);

  useEffect(() => {
    const mount = mountRef.current;
    let raf, disposed = false;
    const width = mount.clientWidth, height = 460;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x08090b);
    const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 4000);
    camera.position.set(0, -20, 14);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.Mesh(new THREE.SphereGeometry(0.3, 20, 20),
      new THREE.MeshBasicMaterial({ color: 0xffcf5e })));
    scene.add(new THREE.AmbientLight(0xffffff, 1));
    for (const p of [...PLANETS, EARTH]) {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(orbitPoints(p).map((v) => v * SCALE), 3));
      scene.add(new THREE.LineLoop(g, new THREE.LineBasicMaterial({
        color: p.color || 0x6f9cff, transparent: true, opacity: 0.3,
      })));
    }

    Object.assign(refs.current, { scene, camera, renderer, controls, points: null, ids: [], highlight: null });

    source.allRecords().then((records) => {
      if (disposed) return;
      const jd = todayJd();
      const pos = [], col = [], ids = [];
      for (const r of records) {
        if (r.epoch_jd == null || r.a_au == null) continue;
        const [p] = propagate(
          { a: r.a_au, e: r.e, i: r.i_deg, om: r.om_deg, w: r.w_deg, ma: r.ma_deg, epoch: r.epoch_jd }, jd);
        if (!Number.isFinite(p[0])) continue;
        pos.push(p[0] * SCALE, p[1] * SCALE, p[2] * SCALE);
        const c = COLOR[r.value_complex] || COLOR.S;
        col.push(c[0], c[1], c[2]);
        ids.push(r.id);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(pos), 3));
      geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(col), 3));
      const points = new THREE.Points(geo, new THREE.PointsMaterial({
        size: 0.07, vertexColors: true, transparent: true, opacity: 0.85,
      }));
      scene.add(points);
      const R = refs.current;
      R.points = points; R.ids = ids;
      setCount(ids.length);
    });

    const raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 0.18;
    const onClick = (e) => {
      const R = refs.current;
      if (!R.points) return;
      const rect = renderer.domElement.getBoundingClientRect();
      const m = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(m, camera);
      const hits = raycaster.intersectObject(R.points);
      if (hits.length) onSelect(R.ids[hits[0].index]);
    };
    renderer.domElement.addEventListener("click", onClick);

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth;
      camera.aspect = w / 460; camera.updateProjectionMatrix(); renderer.setSize(w, 460);
    };
    window.addEventListener("resize", onResize);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.domElement.removeEventListener("click", onClick);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
      refs.current = {};
    };
  }, [onSelect]);

  // highlight the selected object
  useEffect(() => {
    const R = refs.current;
    if (!R.scene || !R.points) return;
    if (R.highlight) { R.scene.remove(R.highlight); R.highlight = null; }
    if (selectedId == null) return;
    const i = R.ids.indexOf(selectedId);
    if (i < 0) return;
    const arr = R.points.geometry.getAttribute("position");
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.18, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xeaeaea }));
    m.position.set(arr.getX(i), arr.getY(i), arr.getZ(i));
    R.scene.add(m);
    R.highlight = m;
  }, [selectedId, count]);

  return (
    <div className="panel">
      <h2 data-idx="04">Catalog Field <span className="note">live positions · {count.toLocaleString()} objects · click to select</span></h2>
      <div className="orbit-wrap">
        <div ref={mountRef} className="orbit-canvas cc" />
        <div className="orbit-legend">
          <span><i style={{ background: "#74757b" }} />C carbon</span>
          <span><i style={{ background: "#b4b6ba" }} />S stony</span>
          <span><i style={{ background: "#f2f2f4" }} />M metallic</span>
          <span><i style={{ background: "#eaeaea", outline: "1px solid #555" }} />selected</span>
        </div>
      </div>
    </div>
  );
}

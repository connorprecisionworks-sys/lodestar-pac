import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

// Real NASA shape models for the famous bodies; everything else uses a generic
// asteroid model. Drop .glb files into frontend/public/models/ (see README).
const MODEL_MAP = [
  [/eros/i, "/models/eros.glb"],
  [/itokawa/i, "/models/itokawa.glb"],
  [/bennu/i, "/models/bennu.glb"],
  [/ryugu/i, "/models/ryugu.glb"],
  [/vesta/i, "/models/vesta.glb"],
  [/ida/i, "/models/ida.glb"],
  [/gaspra/i, "/models/gaspra.glb"],
  [/toutatis/i, "/models/toutatis.glb"],
  [/geographos/i, "/models/geographos.glb"],
  [/golevka/i, "/models/golevka.glb"],
  [/mithra/i, "/models/mithra.glb"],
  [/kleopatra/i, "/models/kleopatra.glb"],
];
// Pool of real shapes used for objects without their own model. Each asteroid
// deterministically picks one by id, so the catalogue shows varied real rocks.
const GENERIC_POOL = [
  "/models/asteroid_hd.glb",  // textured realistic rock
  "/models/asteroid_hd2.glb", // textured realistic rock (variant)
  "/models/toutatis.glb",     // real shape, elongated bilobed
  "/models/golevka.glb",      // real shape, angular
];

function modelFor(detail) {
  for (const [re, url] of MODEL_MAP) if (re.test(detail.full_name)) return url;
  return GENERIC_POOL[Math.abs(detail.id || 0) % GENERIC_POOL.length];
}

export default function AsteroidSpecimen({ detail }) {
  const mountRef = useRef(null);
  const refs = useRef({});
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    const mount = mountRef.current;
    const w = mount.clientWidth, h = 240;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0b0d);
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 100);
    camera.position.set(0, 0, 4);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xfff2dd, 2.2);
    key.position.set(3, 2, 4);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x8090b0, 0.8);
    rim.position.set(-4, -1, -2);
    scene.add(rim);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.enablePan = false;

    Object.assign(refs.current, { scene, camera, renderer, controls, model: null });

    let raf;
    const animate = () => {
      const R = refs.current;
      if (R.model) R.model.rotation.y += 0.003;
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };
    animate();

    const onResize = () => {
      const ww = mount.clientWidth;
      camera.aspect = ww / h; camera.updateProjectionMatrix(); renderer.setSize(ww, h);
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

  // load the model for the selected object
  useEffect(() => {
    const R = refs.current;
    if (!R.scene || !detail) return;
    if (R.model) { R.scene.remove(R.model); R.model = null; }
    setStatus("loading");

    const loader = new GLTFLoader();
    loader.load(
      modelFor(detail),
      (gltf) => {
        const obj = gltf.scene;
        // center + scale to a consistent size
        const box = new THREE.Box3().setFromObject(obj);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        obj.position.sub(center);
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        obj.scale.setScalar(2.2 / maxDim);
        obj.traverse((c) => {
          if (c.isMesh && (!c.material || !c.material.map)) {
            c.material = new THREE.MeshStandardMaterial({ color: 0x9a8f80, roughness: 0.95, metalness: 0.05 });
          }
        });
        R.scene.add(obj);
        R.model = obj;
        setStatus("ok");
      },
      undefined,
      () => setStatus("missing"),
    );
  }, [detail]);

  return (
    <div className="specimen">
      <div ref={mountRef} className="specimen-canvas" />
      {status !== "ok" && (
        <div className="specimen-overlay">
          {status === "loading" ? "Loading model..."
            : "No 3D model installed. Drop .glb files in frontend/public/models/"}
        </div>
      )}
    </div>
  );
}

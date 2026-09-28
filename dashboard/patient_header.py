"""
Persistent patient header — a self-contained "monitor panel" combining the
patient's EHR baseline with a low-poly-but-anatomically-proportioned 3D
figure (Three.js) whose heart glows (cardiac-only build).

Rendered as a single HTML document (via st.iframe) rather than split across
Streamlit columns, so the dark monitor-panel background, patient text, and
the 3D canvas read as one continuous surface instead of stacked widgets.
"""

import streamlit as st

_SEX_LABEL = {1: "Male", 0: "Female"}


def _panel_html(patient_id: str, ehr_profile: dict, height: int = 190) -> str:
    sex_label = _SEX_LABEL.get(ehr_profile.get("sex"), "—")
    age = ehr_profile.get("age", "—")
    chol = ehr_profile.get("chol", "—")
    bp = ehr_profile.get("resting_trestbps", 120)

    return f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; font-family: 'Space Grotesk', sans-serif; }}
      #panel {{
        display: flex; align-items: stretch; height: {height}px;
        background: linear-gradient(145deg, #123037 0%, #0d2529 55%, #0a1e21 100%);
        border-radius: 14px; overflow: hidden; color: #E7EFEC;
        border: 1px solid rgba(255,255,255,0.06);
      }}
      #info {{
        flex: 1.15; padding: 18px 22px; display: flex; flex-direction: column;
        justify-content: center; gap: 10px; min-width: 0;
      }}
      #pid {{
        font-size: 0.98rem; font-weight: 600; letter-spacing: 0.01em;
        display: flex; align-items: center; gap: 8px;
      }}
      #pid .dot {{
        width: 8px; height: 8px; border-radius: 50%; background: #37D6C4;
        box-shadow: 0 0 8px #37D6C4; flex-shrink: 0;
      }}
      #stats {{ display: flex; gap: 26px; flex-wrap: wrap; }}
      .stat-label {{
        font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em;
        color: rgba(231,239,236,0.5); margin-bottom: 3px;
      }}
      .stat-value {{
        font-family: 'IBM Plex Mono', monospace; font-size: 1.15rem;
        font-weight: 600; color: #E7EFEC;
      }}
      #viewing {{
        font-size: 0.72rem; color: rgba(231,239,236,0.55); margin-top: 2px;
      }}
      #viewing b {{ color: #FF6B81; }}
      #model {{ flex: 1; position: relative; min-width: 0; }}
      #twin3d {{ width: 100%; height: 100%; }}
    </style>

    <div id="panel">
      <div id="info">
        <div id="pid"><span class="dot"></span>{patient_id}</div>
        <div id="stats">
          <div><div class="stat-label">Age</div><div class="stat-value">{age}</div></div>
          <div><div class="stat-label">Sex</div><div class="stat-value">{sex_label}</div></div>
          <div><div class="stat-label">Cholesterol</div><div class="stat-value">{chol}</div></div>
          <div><div class="stat-label">Resting BP</div><div class="stat-value">{bp}</div></div>
        </div>
        <div id="viewing">Viewing <b>Cardiac</b> — heart highlighted on the model &rarr;</div>
      </div>
      <div id="model"><div id="twin3d"></div></div>
    </div>

    <script src="https://unpkg.com/three@0.128.0/build/three.min.js"></script>
    <script>
    (function() {{
        const container = document.getElementById('twin3d');
        const width = container.clientWidth || 260;
        const height = {height};

        const scene = new THREE.Scene();
        scene.background = null;

        const camera = new THREE.PerspectiveCamera(32, width / height, 0.1, 100);
        camera.position.set(0.15, 0.25, 5.6);

        const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);

        // --- Lighting: three-point setup for a rounder, less flat look ---
        scene.add(new THREE.HemisphereLight(0xeaf2ff, 0xa9805e, 0.55));

        const key = new THREE.DirectionalLight(0xfff2e0, 1.05);
        key.position.set(2.2, 3.4, 3.2);
        key.castShadow = true;
        key.shadow.mapSize.set(512, 512);
        key.shadow.radius = 4;
        scene.add(key);

        const fill = new THREE.DirectionalLight(0xcfe0ff, 0.32);
        fill.position.set(-2.6, 1.0, 1.6);
        scene.add(fill);

        const rim = new THREE.DirectionalLight(0xff6b81, 0.55);
        rim.position.set(-1.2, 2.0, -3.0);
        scene.add(rim);

        // --- Materials ---
        const skinMat = new THREE.MeshPhysicalMaterial({{
            color: 0xd9a988, roughness: 0.55, clearcoat: 0.12, clearcoatRoughness: 0.6,
        }});
        const hairMat = new THREE.MeshStandardMaterial({{ color: 0x2b2320, roughness: 0.75 }});
        const garmentMat = new THREE.MeshStandardMaterial({{ color: 0xe7ece9, roughness: 0.85 }});

        const body = new THREE.Group();

        function mesh(geo, mat, x, y, z, rx, ry, rz) {{
            const m = new THREE.Mesh(geo, mat);
            m.position.set(x, y, z);
            if (rx) m.rotation.x = rx;
            if (ry) m.rotation.y = ry;
            if (rz) m.rotation.z = rz;
            m.castShadow = true;
            body.add(m);
            return m;
        }}

        // Head — slightly oval, not a perfect sphere.
        const head = mesh(new THREE.SphereGeometry(0.34, 20, 16), skinMat, 0, 1.62, 0);
        head.scale.set(0.86, 1.05, 0.92);

        // Jaw hint + ears for a less egg-like silhouette.
        mesh(new THREE.SphereGeometry(0.2, 14, 10), skinMat, 0, 1.44, 0.05).scale.set(0.85, 0.6, 0.8);
        mesh(new THREE.SphereGeometry(0.045, 8, 8), skinMat, -0.29, 1.6, 0.0);
        mesh(new THREE.SphereGeometry(0.045, 8, 8), skinMat, 0.29, 1.6, 0.0);

        // Hair cap.
        const hair = mesh(new THREE.SphereGeometry(0.36, 20, 16), hairMat, 0, 1.68, -0.02);
        hair.scale.set(0.92, 0.72, 0.98);

        // Eyes.
        mesh(new THREE.SphereGeometry(0.035, 8, 8), hairMat, -0.12, 1.63, 0.29);
        mesh(new THREE.SphereGeometry(0.035, 8, 8), hairMat, 0.12, 1.63, 0.29);

        // Neck.
        mesh(new THREE.CylinderGeometry(0.11, 0.13, 0.18, 12), skinMat, 0, 1.32, 0);

        // Torso — tapered cylinder (wide chest, narrow waist) instead of a box.
        const torso = mesh(new THREE.CylinderGeometry(0.42, 0.28, 0.88, 14), garmentMat, 0, 0.78, 0);

        // Hips / pelvis — flares back out below the waist.
        mesh(new THREE.CylinderGeometry(0.3, 0.26, 0.22, 14), garmentMat, 0, 0.32, 0);

        // Shoulders (joints) + arms (upper + forearm + hand), slightly bent inward.
        function arm(sign) {{
            const shoulderX = sign * 0.46;
            mesh(new THREE.SphereGeometry(0.115, 12, 10), garmentMat, shoulderX, 1.07, 0);

            const upper = mesh(
                new THREE.CylinderGeometry(0.095, 0.08, 0.52, 10), garmentMat,
                shoulderX + sign * 0.05, 0.82, 0.02, 0, 0, sign * 0.22
            );
            const elbowY = 0.56, elbowX = shoulderX + sign * 0.12;
            mesh(new THREE.SphereGeometry(0.08, 10, 8), skinMat, elbowX, elbowY, 0.03);

            mesh(
                new THREE.CylinderGeometry(0.075, 0.06, 0.46, 10), skinMat,
                elbowX + sign * 0.02, 0.32, 0.08, 0, 0, sign * 0.1
            );
            const hand = mesh(new THREE.SphereGeometry(0.075, 10, 8), skinMat, elbowX + sign * 0.03, 0.07, 0.11);
            hand.scale.set(0.75, 1.15, 0.55);
        }}
        arm(-1);
        arm(1);

        // Legs (thigh + shin + foot), hip-width stance.
        function leg(sign) {{
            const hipX = sign * 0.16;
            mesh(new THREE.SphereGeometry(0.13, 10, 8), garmentMat, hipX, 0.2, 0);
            mesh(new THREE.CylinderGeometry(0.135, 0.11, 0.62, 12), garmentMat, hipX, -0.14, 0);
            mesh(new THREE.SphereGeometry(0.1, 10, 8), skinMat, hipX, -0.46, 0.01);
            mesh(new THREE.CylinderGeometry(0.09, 0.075, 0.58, 12), skinMat, hipX, -0.78, 0);
            const foot = mesh(new THREE.BoxGeometry(0.13, 0.08, 0.26), skinMat, hipX, -1.06, 0.07);
            foot.rotation.x = -0.05;
        }}
        leg(-1);
        leg(1);

        // Heart — always highlighted (cardiac-only build), gently pulsing.
        const heartMat = new THREE.MeshStandardMaterial({{
            color: 0xff4462, emissive: 0xff2d47, emissiveIntensity: 0.85, roughness: 0.4,
        }});
        const heart = mesh(new THREE.SphereGeometry(0.1, 14, 10), heartMat, -0.1, 0.94, 0.22);
        const heartGlow = new THREE.PointLight(0xff4462, 1.1, 1.4);
        heartGlow.position.copy(heart.position);
        body.add(heartGlow);

        // Contact shadow (shadow-only material — no visible disc, just the falloff).
        const ground = new THREE.Mesh(
            new THREE.CircleGeometry(1.3, 32),
            new THREE.ShadowMaterial({{ opacity: 0.28 }})
        );
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -1.11;
        ground.receiveShadow = true;
        body.add(ground);

        scene.add(body);

        let t = 0;
        function animate() {{
            requestAnimationFrame(animate);
            t += 0.016;
            body.rotation.y = Math.sin(t * 0.35) * 0.42;             // gentle idle sway
            torso.scale.y = 1 + Math.sin(t * 1.7) * 0.012;           // subtle breathing
            const pulse = 1 + Math.sin(t * 4.2) * 0.16;              // heartbeat pulse
            heart.scale.setScalar(pulse);
            heartGlow.intensity = 0.9 + Math.sin(t * 4.2) * 0.4;
            renderer.render(scene, camera);
        }}
        animate();
    }})();
    </script>
    """


def render_patient_header(patient_id: str, ehr_profile: dict) -> None:
    """Render the persistent monitor-panel header: EHR summary + 3D figure
    with the heart highlighted and gently pulsing."""
    st.iframe(src=_panel_html(patient_id, ehr_profile), height=190)

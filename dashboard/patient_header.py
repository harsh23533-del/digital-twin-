"""
Persistent patient header (Feature: 3D patient model).

Renders a header, shown above the module tabs on every screen, with:
- Patient identity + EHR baseline summary (age, sex, cholesterol, BP)
- A low-poly 3D humanoid (Three.js, embedded via st.components.v1.html)
  that highlights the organ relevant to whichever module tab is active
  (cardiac -> heart, metabolic -> kidney/liver region, dermatology ->
  whole-body skin tint).

The active module has to come from Python (Streamlit's built-in
st.tabs() doesn't expose which tab is selected back to the server), so
app.py drives this with a session-state-backed segmented control
instead of st.tabs — see `_module_selector()` in app.py.
"""

import streamlit as st

_ORGAN_COLORS = {
    "cardiac": "0xe63946",       # heart — red
    "metabolic": "0xf4a261",     # kidney/liver region — amber
    "dermatology": "0x2a9d8f",   # whole-body skin tint — teal
}

_SEX_LABEL = {1: "Male", 0: "Female"}


def _humanoid_html(active_module: str, height: int = 300) -> str:
    """Build the self-contained Three.js scene as an HTML string."""
    highlight_color = _ORGAN_COLORS.get(active_module, "0xe63946")
    highlight_heart = "true" if active_module == "cardiac" else "false"
    highlight_abdomen = "true" if active_module == "metabolic" else "false"
    highlight_skin = "true" if active_module == "dermatology" else "false"

    return f"""
    <div id="twin3d" style="width:100%; height:{height}px;"></div>
    <script src="https://unpkg.com/three@0.128.0/build/three.min.js"></script>
    <script>
    (function() {{
        const container = document.getElementById('twin3d');
        const width = container.clientWidth || 320;
        const height = {height};

        const scene = new THREE.Scene();
        scene.background = null;

        const camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 100);
        camera.position.set(0, 0.2, 5.2);

        const renderer = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
        renderer.setSize(width, height);
        container.appendChild(renderer.domElement);

        scene.add(new THREE.AmbientLight(0xffffff, 0.65));
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(2, 3, 4);
        scene.add(dirLight);

        const skinColor = {highlight_skin} ? {highlight_color} : 0xd8b592;
        const bodyMat = new THREE.MeshStandardMaterial({{ color: skinColor, roughness: 0.6 }});

        const body = new THREE.Group();

        // Low-poly humanoid built from primitives.
        const head = new THREE.Mesh(new THREE.SphereGeometry(0.38, 10, 8), bodyMat);
        head.position.set(0, 1.55, 0);
        body.add(head);

        const torso = new THREE.Mesh(new THREE.BoxGeometry(0.9, 1.25, 0.5), bodyMat);
        torso.position.set(0, 0.55, 0);
        body.add(torso);

        const armGeo = new THREE.CylinderGeometry(0.11, 0.11, 1.1, 8);
        const armL = new THREE.Mesh(armGeo, bodyMat);
        armL.position.set(-0.62, 0.55, 0);
        armL.rotation.z = 0.15;
        body.add(armL);
        const armR = new THREE.Mesh(armGeo, bodyMat);
        armR.position.set(0.62, 0.55, 0);
        armR.rotation.z = -0.15;
        body.add(armR);

        const legGeo = new THREE.CylinderGeometry(0.14, 0.14, 1.3, 8);
        const legL = new THREE.Mesh(legGeo, bodyMat);
        legL.position.set(-0.24, -0.85, 0);
        body.add(legL);
        const legR = new THREE.Mesh(legGeo, bodyMat);
        legR.position.set(0.24, -0.85, 0);
        body.add(legR);

        // Organ markers — always present, lit up when their module is active.
        const heartColor = {highlight_heart} ? {highlight_color} : 0x8a8a8a;
        const heartEmissive = {highlight_heart} ? {highlight_color} : 0x000000;
        const heartMat = new THREE.MeshStandardMaterial({{
            color: heartColor, emissive: heartEmissive, emissiveIntensity: 0.5
        }});
        const heart = new THREE.Mesh(new THREE.SphereGeometry(0.14, 10, 8), heartMat);
        heart.position.set(-0.12, 0.78, 0.28);
        body.add(heart);

        const abdomenColor = {highlight_abdomen} ? {highlight_color} : 0x8a8a8a;
        const abdomenEmissive = {highlight_abdomen} ? {highlight_color} : 0x000000;
        const abdomenMat = new THREE.MeshStandardMaterial({{
            color: abdomenColor, emissive: abdomenEmissive, emissiveIntensity: 0.5
        }});
        const kidneyL = new THREE.Mesh(new THREE.SphereGeometry(0.1, 8, 6), abdomenMat);
        kidneyL.position.set(-0.2, 0.25, 0.22);
        body.add(kidneyL);
        const kidneyR = new THREE.Mesh(new THREE.SphereGeometry(0.1, 8, 6), abdomenMat);
        kidneyR.position.set(0.2, 0.25, 0.22);
        body.add(kidneyR);
        const liver = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.2, 0.18), abdomenMat);
        liver.position.set(0.15, 0.35, 0.25);
        body.add(liver);

        scene.add(body);

        let t = 0;
        function animate() {{
            requestAnimationFrame(animate);
            t += 0.006;
            body.rotation.y = Math.sin(t) * 0.5;  // gentle sway, not a full spin
            renderer.render(scene, camera);
        }}
        animate();
    }})();
    </script>
    """


def render_patient_header(patient_id: str, ehr_profile: dict, active_module: str) -> None:
    """Render the persistent header: EHR summary + 3D humanoid, organ-highlighted
    for the currently active module tab. Kept compact (fixed small height) so it
    doesn't push the live charts below the fold."""
    with st.container(border=True):
        info_col, model_col = st.columns([1, 1])

        with info_col:
            st.markdown(f"**🧑‍⚕️ {patient_id}**")
            sex_label = _SEX_LABEL.get(ehr_profile.get("sex"), "—")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Age", ehr_profile.get("age", "—"))
            c2.metric("Sex", sex_label)
            c3.metric("Chol.", f"{ehr_profile.get('chol', '—')}")
            c4.metric("BP", f"{ehr_profile.get('resting_trestbps', 120)}")
            module_names = {"cardiac": "Cardiac", "metabolic": "Metabolic", "dermatology": "Dermatology"}
            viewing = module_names.get(active_module, active_module)
            st.caption(f"Viewing: **{viewing}** — organ highlighted on the model →")

        with model_col:
            st.iframe(src=_humanoid_html(active_module, height=150), height=150)

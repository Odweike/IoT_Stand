(() => {
  const telemetryEl = document.getElementById("telemetry");
  const statusEl = document.getElementById("ws-status");

  function connectWS() {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/telemetry`);
    ws.onopen = () => statusEl.textContent = "connected";
    ws.onclose = () => {
      statusEl.textContent = "disconnected";
      setTimeout(connectWS, 1000);
    };
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        telemetryEl.textContent = JSON.stringify(payload, null, 2);
        updateTelemetryFields(payload);
      } catch {
        telemetryEl.textContent = event.data;
      }
    };
  }

  function updateTelemetryFields(payload) {
    const t1 = document.getElementById("t1-value");
    const t2 = document.getElementById("t2-value");
    const t3 = document.getElementById("t3-value");
    const drain = document.getElementById("drain-valve-state");
    if (t1) t1.textContent = payload.t1 ?? "n/a";
    if (t2) t2.textContent = payload.t2 ?? "n/a";
    if (t3) t3.textContent = payload.t3 ?? "n/a";
    if (drain) {
      if (payload.drain_valve === 0) drain.textContent = "closed";
      else if (payload.drain_valve === 1) drain.textContent = "open";
      else drain.textContent = "unknown";
    }
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    connectWS();

    const manualForm = document.getElementById("heater-manual-form");
    if (manualForm) {
      manualForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const power = Number(document.getElementById("heater-power").value || 0);
        await postJSON("/api/teacher/heater/manual", { power });
      });
    }

    const randomForm = document.getElementById("heater-random-form");
    if (randomForm) {
      randomForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const payload = {
          min: Number(document.getElementById("rand-min").value || 0),
          max: Number(document.getElementById("rand-max").value || 100),
          on_min_s: Number(document.getElementById("rand-on-min").value || 2),
          on_max_s: Number(document.getElementById("rand-on-max").value || 10),
          off_min_s: Number(document.getElementById("rand-off-min").value || 2),
          off_max_s: Number(document.getElementById("rand-off-max").value || 10)
        };
        await postJSON("/api/teacher/heater/random", payload);
      });
    }

    const stopBtn = document.getElementById("heater-stop");
    if (stopBtn) {
      stopBtn.addEventListener("click", async () => {
        await postJSON("/api/teacher/heater/stop", {});
      });
    }

    const drainOpen = document.getElementById("drain-open");
    const drainClose = document.getElementById("drain-close");
    if (drainOpen) {
      drainOpen.addEventListener("click", async () => {
        await postJSON("/api/teacher/drain_valve", { open: true });
      });
    }
    if (drainClose) {
      drainClose.addEventListener("click", async () => {
        await postJSON("/api/teacher/drain_valve", { open: false });
      });
    }

    const modeBaseline = document.getElementById("mode-baseline");
    const modeStudent = document.getElementById("mode-student");
    const modeStatus = document.getElementById("student-mode-status");
    async function refreshMode() {
      if (!modeStatus) return;
      const resp = await fetch("/api/teacher/student_mode");
      const json = await resp.json();
      modeStatus.textContent = json.mode || "unknown";
      if (json.warning) {
        const warn = document.getElementById("mode-warning");
        if (warn) warn.textContent = json.warning;
      }
    }
    if (modeBaseline) {
      modeBaseline.addEventListener("click", async () => {
        const resp = await postJSON("/api/teacher/student_mode", { mode: "baseline" });
        const json = await resp.json();
        if (modeStatus) modeStatus.textContent = json.mode || "baseline";
        const warn = document.getElementById("mode-warning");
        if (warn) warn.textContent = json.warning || "";
      });
    }
    if (modeStudent) {
      modeStudent.addEventListener("click", async () => {
        const resp = await postJSON("/api/teacher/student_mode", { mode: "student" });
        const json = await resp.json();
        if (modeStatus) modeStatus.textContent = json.mode || "student";
        const warn = document.getElementById("mode-warning");
        if (warn) warn.textContent = json.warning || "";
      });
    }
    refreshMode();

    const actuatorsForm = document.getElementById("actuators-form");
    if (actuatorsForm) {
      actuatorsForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const payload = {
          pump: Number(document.getElementById("pump").value || 0),
          fan: [
            Number(document.getElementById("fan1").value || 0),
            Number(document.getElementById("fan2").value || 0),
            Number(document.getElementById("fan3").value || 0)
          ]
        };
        await postJSON("/api/student/actuators", payload);
      });
    }

    const firmwareForm = document.getElementById("firmware-form");
    if (firmwareForm) {
      firmwareForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById("firmware-file");
        const boardInput = document.getElementById("board-fqbn");
        const sketchInput = document.getElementById("sketch-main");
        const status = document.getElementById("firmware-status");
        const data = new FormData();
        if (fileInput.files.length === 0) {
          status.textContent = "choose a file";
          return;
        }
        data.append("file", fileInput.files[0]);
        data.append("board_fqbn", boardInput.value || "arduino:avr:uno");
        if (sketchInput.value) {
          data.append("sketch_main", sketchInput.value);
        }
        status.textContent = "uploading...";
        const resp = await fetch("/api/student/firmware/upload", { method: "POST", body: data });
        const json = await resp.json();
        status.textContent = JSON.stringify(json, null, 2);
      });
    }
  });
})();

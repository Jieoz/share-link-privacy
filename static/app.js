(() => {
  const $ = (id) => document.getElementById(id);
  const urlInput = $("url");
  const goBtn = $("go");
  const hint = $("hint");
  const status = $("status");
  const result = $("result");
  const platforms = $("platforms");

  function setStatus(text, kind) {
    if (!text) {
      status.hidden = true;
      status.textContent = "";
      return;
    }
    status.hidden = false;
    status.textContent = text;
    status.dataset.kind = kind || "";
  }

  function renderResult(data) {
    result.hidden = false;
    result.innerHTML = "";
    if (!data || data.ok === false) {
      setStatus((data && data.msg) || "解析失败", "error");
      result.hidden = true;
      return;
    }
    if (data.safe) {
      setStatus(data.msg || "未发现分享人的账号", "safe");
      result.hidden = true;
      return;
    }
    setStatus("");
    const who = document.createElement("div");
    who.className = "who";
    if (data.avatar) {
      const img = document.createElement("img");
      img.src = data.avatar.startsWith("//") ? "https:" + data.avatar : data.avatar;
      img.alt = "avatar";
      img.referrerPolicy = "no-referrer";
      who.appendChild(img);
    }
    if (data.name) {
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = data.name;
      who.appendChild(name);
    } else if (data.id) {
      const name = document.createElement("div");
      name.className = "name";
      name.textContent = data.id;
      who.appendChild(name);
    }
    result.appendChild(who);

    if (data.url) {
      const link = document.createElement("div");
      link.className = "meta";
      const a = document.createElement("a");
      a.href = data.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = data.url;
      link.appendChild(a);
      result.appendChild(link);
    }

    const meta = document.createElement("div");
    meta.className = "meta";
    const bits = [];
    if (data.platform) bits.push(data.platform);
    if (data.id) bits.push("id=" + data.id);
    if (data.msg) bits.push(data.msg);
    meta.textContent = bits.join(" · ");
    result.appendChild(meta);
  }

  async function query() {
    const url = (urlInput.value || "").trim();
    if (!url) {
      setStatus("请先粘贴链接", "error");
      result.hidden = true;
      return;
    }
    goBtn.disabled = true;
    hint.hidden = true;
    setStatus("解析中…", "loading");
    result.hidden = true;
    const started = Date.now();
    try {
      const resp = await fetch("/api/parse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();
      const wait = 400 - (Date.now() - started);
      if (wait > 0) await new Promise((r) => setTimeout(r, wait));
      renderResult(data);
    } catch (err) {
      setStatus("网络或服务异常，请稍后重试", "error");
      result.hidden = true;
    } finally {
      goBtn.disabled = false;
    }
  }

  goBtn.addEventListener("click", query);
  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") query();
  });

  fetch("/api/platforms")
    .then((r) => r.json())
    .then((data) => {
      (data.platforms || []).forEach((name) => {
        const li = document.createElement("li");
        li.textContent = name;
        platforms.appendChild(li);
      });
    })
    .catch(() => {});
})();

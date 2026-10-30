/* ============ EchoID auth (client-side demo only) ============ */
/* Passwords here are stored base64-encoded in localStorage purely so the mock
   flow works offline. This is NOT authentication — do not reuse for real. */

(() => {
  const nextUrl = () => {
    const n = new URLSearchParams(location.search).get("next");
    return n && /^[\w.-]+\.html$/.test(n) ? n : "dashboard.html";
  };

  const setError = (form, name, msg) => {
    const slot = form.querySelector(`.field__error[data-for="${name}"]`);
    if (slot) slot.textContent = msg || "";
  };
  const clearErrors = (form) => form.querySelectorAll(".field__error").forEach((e) => (e.textContent = ""));
  const validEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

  /* ---------- login ---------- */
  const loginForm = document.getElementById("loginForm");
  loginForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    clearErrors(loginForm);
    const email = loginForm.email.value.trim();
    const pass = loginForm.password.value;
    let ok = true;
    if (!email) { setError(loginForm, "email", "Email is required."); ok = false; }
    else if (!validEmail(email)) { setError(loginForm, "email", "Enter a valid email."); ok = false; }
    if (!pass) { setError(loginForm, "password", "Password is required."); ok = false; }
    if (!ok) return;

    const user = ECHO.findAccount(email);
    if (!user || user.pass !== btoa(pass)) {
      setError(loginForm, "password", "Incorrect email or password.");
      ECHO.toast("Those details don't match an account.");
      return;
    }
    ECHO.signIn(user.email);
    ECHO.toast(`Welcome back, ${user.name.split(" ")[0]}!`);
    setTimeout(() => (location.href = nextUrl()), 700);
  });

  /* ---------- register ---------- */
  const regForm = document.getElementById("registerForm");
  regForm?.addEventListener("submit", (e) => {
    e.preventDefault();
    clearErrors(regForm);
    const name = regForm.name.value.trim();
    const email = regForm.email.value.trim();
    const pass = regForm.password.value;
    const confirm = regForm.confirm.value;
    let ok = true;
    if (name.length < 2) { setError(regForm, "name", "Please enter your name."); ok = false; }
    if (!validEmail(email)) { setError(regForm, "email", "Enter a valid email."); ok = false; }
    else if (ECHO.findAccount(email)) { setError(regForm, "email", "That email already has an account."); ok = false; }
    if (pass.length < 6) { setError(regForm, "password", "Use at least 6 characters."); ok = false; }
    if (pass !== confirm) { setError(regForm, "confirm", "Passwords don't match."); ok = false; }
    if (!ok) return;

    ECHO.saveAccount({ name, email, pass: btoa(pass), plan: regForm.plan.value, createdAt: Date.now() });
    ECHO.signIn(email);
    ECHO.toast("Account created — welcome to EchoID!");
    setTimeout(() => (location.href = nextUrl()), 800);
  });
})();

const COPY = {
  signin: {
    title: "Welcome back",
    sub: "Sign in to your workspace to keep generating.",
    submit: "Sign in",
    busy: "Signing in…",
    autocomplete: "current-password",
  },
  signup: {
    title: "Create your workspace",
    sub: "Start free with 20 faces on the house — no card needed.",
    submit: "Create account",
    busy: "Creating workspace…",
    autocomplete: "new-password",
  },
};

const tabs = document.querySelectorAll(".auth-tab");
const authForm = document.getElementById("authForm");
const authTitle = document.getElementById("authTitle");
const authSub = document.getElementById("authSub");
const authSubmit = document.getElementById("authSubmit");
const authStatus = document.getElementById("authStatus");
const nameField = document.getElementById("nameField");
const authName = document.getElementById("authName");
const authEmail = document.getElementById("authEmail");
const authPassword = document.getElementById("authPassword");
const pwToggle = document.getElementById("pwToggle");
const forgotLink = document.getElementById("forgotLink");

let mode = new URLSearchParams(location.search).get("mode") === "signup" ? "signup" : "signin";

function applyMode(next) {
  mode = next;
  const copy = COPY[mode];
  const isSignup = mode === "signup";

  tabs.forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset.mode === mode));
  });

  authTitle.textContent = copy.title;
  authSub.textContent = copy.sub;
  authSubmit.textContent = copy.submit;
  authStatus.textContent = "";

  nameField.classList.toggle("is-hidden", !isSignup);
  authName.required = isSignup;
  authPassword.autocomplete = copy.autocomplete;
  document.title = `${isSignup ? "Create account" : "Sign in"} — Faceform`;
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => applyMode(tab.dataset.mode));
});

pwToggle.addEventListener("click", () => {
  const show = authPassword.type === "password";
  authPassword.type = show ? "text" : "password";
  pwToggle.textContent = show ? "Hide" : "Show";
  pwToggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
});

authForm.addEventListener("submit", (event) => {
  event.preventDefault();

  if (!authForm.checkValidity()) {
    authStatus.textContent = "Check the highlighted fields and try again.";
    authForm.reportValidity();
    return;
  }

  authSubmit.disabled = true;
  authSubmit.textContent = COPY[mode].busy;
  authStatus.textContent =
    mode === "signup"
      ? "Setting up your workspace and 20 free credits…"
      : "Signing you in…";

  setTimeout(() => {
    window.location.href = "dashboard.html";
  }, 950);
});

document.querySelectorAll("[data-provider]").forEach((button) => {
  button.addEventListener("click", () => {
    authStatus.textContent = `Redirecting to ${button.dataset.provider}…`;
    FF.toast(`Connecting to ${button.dataset.provider}`);
    setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 900);
  });
});

forgotLink.addEventListener("click", (event) => {
  event.preventDefault();
  const email = authEmail.value.trim();
  if (!email) {
    FF.toast("Enter your email first");
    authEmail.focus();
    return;
  }
  FF.toast(`Reset link sent to ${email}`);
});

applyMode(mode);

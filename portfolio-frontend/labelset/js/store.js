/* Labelset — localStorage-backed demo data layer */
(function () {
  "use strict";

  const DB_KEY = "labelset_db_v1";
  const SESSION_KEY = "labelset_session_v1";

  const uid = p => p + "_" + Math.random().toString(36).slice(2, 9);
  const now = () => new Date().toISOString();
  const daysAgo = n => new Date(Date.now() - n * 864e5).toISOString();

  function seed() {
    const ada = { id: "u_ada", name: "Ada Lovelace", email: "ada@mail.com", password: "demo1234", kind: "labeler", skills: ["Audio", "Image"], balance: 42.5, joined: daysAgo(90) };
    const lin = { id: "u_lin", name: "Lin Zhao", email: "lin@mail.com", password: "demo1234", kind: "labeler", skills: ["Video"], balance: 12, joined: daysAgo(40) };
    const sam = { id: "u_sam", name: "Sam Rivera", email: "sam@acme.ai", password: "demo1234", kind: "labeler", skills: ["Image"], balance: 0, joined: daysAgo(120) };
    const kim = { id: "u_kim", name: "Kim Osei", email: "kim@acme.ai", password: "demo1234", kind: "labeler", skills: ["Audio"], balance: 5, joined: daysAgo(60) };

    const org = {
      id: "o_acme", name: "Acme Vision Labs", industry: "Autonomous systems",
      ownerId: "u_sam", code: "ACME-2026", balance: 500, card: null,
      members: ["u_sam", "u_kim"], requests: [], createdAt: daysAgo(200)
    };

    const dsAudio = { id: "d_audio", orgId: org.id, name: "Call Center EN Q3", type: "Audio", items: 60, sizeMB: 812, uploadedAt: daysAgo(21) };
    const dsImage = { id: "d_image", orgId: org.id, name: "Retail Shelf Scan", type: "Image", items: 80, sizeMB: 1440, uploadedAt: daysAgo(14) };
    const dsVideo = { id: "d_video", orgId: org.id, name: "Street Cam Clips", type: "Video", items: 40, sizeMB: 5120, uploadedAt: daysAgo(7) };

    const pAudio = { id: "p_audio", orgId: org.id, datasetId: dsAudio.id, title: "Call intent labeling", type: "Audio", reward: 2, status: "open", createdAt: daysAgo(20) };
    const pImage = { id: "p_image", orgId: org.id, datasetId: dsImage.id, title: "Shelf out-of-stock detection", type: "Image", reward: 1.5, status: "open", createdAt: daysAgo(12) };
    const pVideo = { id: "p_video", orgId: org.id, datasetId: dsVideo.id, title: "Pedestrian event tagging", type: "Video", reward: 4, status: "open", createdAt: daysAgo(5) };

    const mkTask = (p, status, extra = {}) => Object.assign({
      id: uid("t"), projectId: p.id, orgId: p.orgId, reward: p.reward,
      status, labelerId: null, question: `${p.type} item review — classify the dominant label`,
      options: ["Valid", "Invalid", "Needs review"], answer: "", note: "",
      assignedAt: null, submittedAt: null, reviewedAt: null, reviewNote: ""
    }, extra);

    const tasks = [
      mkTask(pAudio, "approved", { labelerId: ada.id, answer: "Valid", submittedAt: daysAgo(6), reviewedAt: daysAgo(5), assignedAt: daysAgo(8) }),
      mkTask(pAudio, "approved", { labelerId: ada.id, answer: "Valid", submittedAt: daysAgo(4), reviewedAt: daysAgo(3), assignedAt: daysAgo(5) }),
      mkTask(pAudio, "submitted", { labelerId: ada.id, answer: "Needs review", submittedAt: daysAgo(1), assignedAt: daysAgo(2) }),
      mkTask(pAudio, "assigned", { labelerId: lin.id, assignedAt: daysAgo(1) }),
      mkTask(pAudio, "available"), mkTask(pAudio, "available"),
      mkTask(pImage, "submitted", { labelerId: lin.id, answer: "Invalid", submittedAt: hoursAgoStr(20), assignedAt: daysAgo(2) }),
      mkTask(pImage, "rejected", { labelerId: ada.id, answer: "Valid", note: "Blurry crop", reviewNote: "Please re-check the left shelf region.", submittedAt: daysAgo(3), reviewedAt: daysAgo(2), assignedAt: daysAgo(4) }),
      mkTask(pImage, "available"), mkTask(pImage, "available"), mkTask(pImage, "available"),
      mkTask(pVideo, "available"), mkTask(pVideo, "available"),
      mkTask(pVideo, "assigned", { labelerId: ada.id, assignedAt: daysAgo(1) })
    ];

    return {
      users: [ada, lin, sam, kim],
      orgs: [org],
      invites: [{ id: uid("i"), orgId: org.id, email: "newhire@acme.ai", code: "ACME-X7K2", status: "pending", createdAt: daysAgo(3) }],
      datasets: [dsAudio, dsImage, dsVideo],
      projects: [pAudio, pImage, pVideo],
      tasks,
      payments: [{ id: uid("pay"), orgId: org.id, type: "topup", amount: 1000, desc: "Card ····4242", date: daysAgo(30) },
                 { id: uid("pay"), orgId: org.id, type: "payout", amount: 4, desc: "Task reward → Ada Lovelace", date: daysAgo(5) }],
      withdrawals: [{ id: uid("w"), userId: ada.id, amount: 20, status: "paid", date: daysAgo(10) }],
      notifications: [
        { id: uid("n"), userId: ada.id, text: "Your task was approved — $2.00 added to your balance.", type: "money", read: true, date: daysAgo(5) },
        { id: uid("n"), userId: ada.id, text: "Task rejected: Please re-check the left shelf region.", type: "task", read: false, date: daysAgo(2) },
        { id: uid("n"), userId: sam.id, text: "1 task is waiting for your review.", type: "review", read: false, date: daysAgo(1) }
      ]
    };
  }
  function hoursAgoStr(h) { return new Date(Date.now() - h * 36e5).toISOString(); }

  /* ---------- accessors ---------- */
  function read() {
    let db = JSON.parse(localStorage.getItem(DB_KEY) || "null");
    if (!db) { db = seed(); write(db); }
    return db;
  }
  function write(db) { localStorage.setItem(DB_KEY, JSON.stringify(db)); }
  function reset() { localStorage.removeItem(DB_KEY); localStorage.removeItem(SESSION_KEY); read(); }

  function session() { return localStorage.getItem(SESSION_KEY); }
  function setSession(userId) { userId ? localStorage.setItem(SESSION_KEY, userId) : localStorage.removeItem(SESSION_KEY); }

  function me() {
    const db = read();
    return db.users.find(u => u.id === session()) || null;
  }
  function login(email, password) {
    const db = read();
    const u = db.users.find(x => x.email.toLowerCase() === String(email).toLowerCase().trim());
    if (!u || u.password !== password) return null;
    setSession(u.id);
    return u;
  }
  function logout() { setSession(null); }

  function orgOf(user) {
    if (!user) return null;
    const db = read();
    return db.orgs.find(o => o.ownerId === user.id || o.members.includes(user.id)) || null;
  }
  function ownedOrg(user) {
    if (!user) return null;
    return read().orgs.find(o => o.ownerId === user.id) || null;
  }

  function notify(userId, text, type = "info") {
    const db = read();
    db.notifications.unshift({ id: uid("n"), userId, text, type, read: false, date: now() });
    write(db);
  }

  function fmtDate(iso) { return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }); }
  function fmtAgo(iso) {
    const s = (Date.now() - new Date(iso)) / 1000;
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + "m ago";
    if (s < 86400) return Math.round(s / 3600) + "h ago";
    return Math.round(s / 86400) + "d ago";
  }
  const money = n => "$" + Number(n).toFixed(2);

  /* ---------- verification & payout (single source of truth) ---------- */
  function approveTask(taskId, reviewerId) {
    const db = read();
    const t = db.tasks.find(x => x.id === taskId);
    if (!t || t.status !== "submitted") return { error: "Task is not awaiting review." };
    const org = db.orgs.find(o => o.id === t.orgId);
    if (org.balance < t.reward) return { error: "Organization balance is too low. Add funds in Billing first." };
    const labeler = db.users.find(u => u.id === t.labelerId);
    t.status = "approved"; t.reviewedAt = now();
    org.balance = +(org.balance - t.reward).toFixed(2);
    if (labeler) {
      labeler.balance = +(labeler.balance + t.reward).toFixed(2);
      db.notifications.unshift({ id: uid("n"), userId: labeler.id, text: `Verified! ${money(t.reward)} added to your balance.`, type: "money", read: false, date: now() });
    }
    db.payments.unshift({ id: uid("pay"), orgId: org.id, type: "payout", amount: t.reward, desc: `Task reward → ${labeler ? labeler.name : "labeler"}`, date: now() });
    write(db);
    return { ok: true };
  }

  function rejectTask(taskId, note) {
    const db = read();
    const t = db.tasks.find(x => x.id === taskId);
    if (!t || t.status !== "submitted") return { error: "Task is not awaiting review." };
    t.status = "rejected"; t.reviewedAt = now(); t.reviewNote = note || "Needs another pass.";
    const labeler = db.users.find(u => u.id === t.labelerId);
    if (labeler) db.notifications.unshift({ id: uid("n"), userId: labeler.id, text: `Task returned for revision: ${t.reviewNote}`, type: "task", read: false, date: now() });
    write(db);
    return { ok: true };
  }

  window.Store = {
    uid, read, write, reset, session, setSession, me, login, logout,
    orgOf, ownedOrg, notify, fmtDate, fmtAgo, money,
    approveTask, rejectTask
  };
})();

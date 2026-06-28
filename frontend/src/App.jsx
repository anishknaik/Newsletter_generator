import { useEffect, useState } from "react";
import AuthForm from "./components/AuthForm.jsx";
import NewsletterApp from "./components/NewsletterApp.jsx";
import { getToken, logout, me } from "./api/client.js";

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false); // finished checking stored token?
  const [notice, setNotice] = useState(""); // e.g. "session expired"

  // On load, if we have a stored token, validate it by fetching the user.
  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    me()
      .then(setUser)
      .catch(() => logout())
      .finally(() => setReady(true));
  }, []);

  function handleLogout(reason) {
    logout();
    setUser(null);
    setNotice(typeof reason === "string" ? reason : "");
  }

  if (!ready) return null; // brief blank while validating the token

  if (!user) {
    return (
      <AuthForm
        notice={notice}
        onAuthed={(u) => {
          setNotice("");
          setUser(u);
        }}
      />
    );
  }

  return <NewsletterApp user={user} onLogout={handleLogout} />;
}

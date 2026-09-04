/**
 * login/page.tsx  (served at "/login")
 * ====================================
 * One screen that handles both signing in and creating an account, toggled by
 * a single piece of state. Keeping them together avoids duplicating the form,
 * the validation and the error handling across two nearly identical files.
 *
 * WHAT HAPPENS ON SUBMIT
 * ----------------------
 *   Sign in : POST /auth/login  -> receive a JWT -> save it -> go to dashboard
 *   Sign up : POST /auth/signup -> creates the org and an Admin user
 *                                -> immediately log in with the same details
 *
 * Signing up creates a brand-new ORGANIZATION as well as a user. The person
 * who creates it becomes its Admin. That is what makes the app multi-tenant:
 * each organization's documents are completely isolated from every other one.
 */

"use client";

import { motion } from "framer-motion";
import { AlertCircle, ArrowRight, Loader2, Lock, Mail, Building2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { api, getErrorMessage } from "@/lib/api";

export default function LoginPage() {
  // `useRouter` gives programmatic navigation -- moving the user to another
  // page from inside code, rather than by them clicking a link.
  const router = useRouter();

  // ---- Form state ----------------------------------------------------
  // Each input is a "controlled component": React holds the value in state and
  // the input displays it. That makes the current value available to the
  // submit handler without ever reading the DOM directly.
  const [isSignup, setIsSignup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgName, setOrgName] = useState("");

  // ---- Request state -------------------------------------------------
  // `loading` disables the button and shows a spinner, which prevents the user
  // double-submitting and creating two accounts.
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent) {
    // Stop the browser's default behaviour of reloading the page on submit,
    // which would throw away all our React state.
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      if (isSignup) {
        // Create the organization and its first (Admin) user...
        await api.signup(email, password, orgName);
        // ...then log straight in, so the user is not asked to type the same
        // credentials again immediately.
        await api.login(email, password);
      } else {
        await api.login(email, password);
      }

      // `push` navigates without a full page reload, so the app stays fast.
      router.push("/dashboard");
    } catch (err) {
      // Show the backend's real message ("A user with this email already
      // exists") rather than a generic failure.
      setError(getErrorMessage(err, "Something went wrong. Please try again."));
    } finally {
      // `finally` runs whether or not an error was thrown, so the button can
      // never get permanently stuck in its loading state.
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="glass w-full max-w-md p-8"
      >
        {/* ---- Header ---- */}
        <div className="mb-8 text-center">
          <h1 className="text-gradient text-3xl font-bold">
            {isSignup ? "Create your workspace" : "Welcome back"}
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
            {isSignup
              ? "Set up an organization and start uploading documents."
              : "Sign in to search and question your documents."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Organization name is only relevant when creating an account. */}
          {isSignup && (
            <motion.div
              // Animating the height lets the field slide open smoothly rather
              // than making the whole form jump when it appears.
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="relative"
            >
              <Building2
                size={16}
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2"
                style={{ color: "var(--text-muted)" }}
              />
              <input
                className="input pl-11"
                placeholder="Organization name"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                required={isSignup}
              />
            </motion.div>
          )}

          {/* Email */}
          <div className="relative">
            <Mail
              size={16}
              className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2"
              style={{ color: "var(--text-muted)" }}
            />
            <input
              // type="email" makes mobile browsers show an @-friendly keyboard
              // and gives basic format validation for free.
              type="email"
              className="input pl-11"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          {/* Password */}
          <div className="relative">
            <Lock
              size={16}
              className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2"
              style={{ color: "var(--text-muted)" }}
            />
            <input
              // type="password" masks the characters as they are typed.
              type="password"
              className="input pl-11"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </div>

          {/* Error banner, shown only when there is something to report. */}
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-start gap-2 rounded-xl px-4 py-3 text-sm"
              style={{
                background: "rgba(248,113,113,0.1)",
                color: "var(--danger)",
              }}
            >
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          <button
            type="submit"
            // Disabling during the request is what prevents a double submit.
            disabled={loading}
            className="btn-primary w-full py-3"
          >
            {loading ? (
              <>
                {/* `animate-spin` is a Tailwind utility that rotates the icon
                    continuously, giving a standard loading spinner. */}
                <Loader2 size={16} className="animate-spin" />
                {isSignup ? "Creating workspace..." : "Signing in..."}
              </>
            ) : (
              <>
                {isSignup ? "Create workspace" : "Sign in"}
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* Toggle between the two modes */}
        <div className="mt-6 text-center text-sm">
          <span style={{ color: "var(--text-muted)" }}>
            {isSignup ? "Already have an account?" : "No account yet?"}
          </span>{" "}
          <button
            onClick={() => {
              setIsSignup(!isSignup);
              // Clear any stale error so a message from the previous mode does
              // not linger confusingly over the new form.
              setError("");
            }}
            className="font-medium transition-colors"
            style={{ color: "var(--accent-hover)" }}
          >
            {isSignup ? "Sign in" : "Create one"}
          </button>
        </div>
      </motion.div>
    </main>
  );
}

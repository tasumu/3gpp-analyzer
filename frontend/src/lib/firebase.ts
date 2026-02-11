/**
 * Firebase client configuration and initialization.
 *
 * Firebase App Hosting automatically sets FIREBASE_WEBAPP_CONFIG,
 * so initializeApp() can be called without arguments.
 * See: https://firebase.google.com/docs/app-hosting/firebase-sdks
 */

import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

// Initialize Firebase only once
let app: FirebaseApp;
let auth: Auth;

function getFirebaseApp(): FirebaseApp {
  if (!app) {
    // Firebase App Hosting sets FIREBASE_WEBAPP_CONFIG automatically
    // initializeApp() without arguments uses this auto-configuration
    app = getApps().length === 0 ? initializeApp() : getApps()[0];
  }
  return app;
}

function getFirebaseAuth(): Auth {
  if (!auth) {
    auth = getAuth(getFirebaseApp());
    // Use app's own domain as authDomain so the auth flow is first-party.
    // This works with the /__/auth/* rewrite in next.config.ts.
    if (typeof window !== "undefined") {
      auth.config.authDomain = window.location.host;
    }
  }
  return auth;
}

export { getFirebaseApp, getFirebaseAuth };

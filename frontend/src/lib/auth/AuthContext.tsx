"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  type User,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as firebaseSignOut,
  onAuthStateChanged,
} from "firebase/auth";
import { getFirebaseAuth } from "../firebase";
import { registerUser, getCurrentUserInfo } from "../api";
import type { UserInfo } from "../types";

interface AuthContextType {
  user: User | null;
  userInfo: UserInfo | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const googleProvider = new GoogleAuthProvider();

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const auth = getFirebaseAuth();
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setUser(user);

      if (user) {
        try {
          // Register user in backend or update last login time
          // Email is automatically extracted from the Firebase ID token
          const info = await registerUser(user.displayName || undefined);
          setUserInfo(info);
        } catch (error) {
          console.error("Failed to register user:", error);
          // Try to get current user info as fallback
          try {
            const info = await getCurrentUserInfo();
            setUserInfo(info);
          } catch {
            setUserInfo(null);
          }
        }
      } else {
        setUserInfo(null);
      }

      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signInWithGoogle = async () => {
    const auth = getFirebaseAuth();
    await signInWithPopup(auth, googleProvider);
  };

  const signOut = async () => {
    const auth = getFirebaseAuth();
    await firebaseSignOut(auth);
  };

  const getIdToken = async (): Promise<string | null> => {
    if (!user) return null;
    return user.getIdToken();
  };

  return (
    <AuthContext.Provider
      value={{ user, userInfo, loading, signInWithGoogle, signOut, getIdToken }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

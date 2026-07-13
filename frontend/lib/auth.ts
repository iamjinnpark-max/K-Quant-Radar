"use client";

import { currentUser, logoutRequest } from "./authClient";

export const authEnabled = true;

export async function currentSession() {
  const user = await currentUser();
  if (!user) throw new Error("Authentication required");
  return {
    token: "",
    username: user.email,
  };
}

export async function login() {
  location.assign("/login");
}

export async function logout() {
  await logoutRequest();
  location.assign("/login");
}

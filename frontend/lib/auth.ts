"use client";

import { Amplify } from "aws-amplify";
import {
  fetchAuthSession,
  getCurrentUser,
  signInWithRedirect,
  signOut,
} from "aws-amplify/auth";

export const authEnabled =
  process.env.NEXT_PUBLIC_AUTH_MODE === "cognito";

if (authEnabled) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID!,
        userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID!,
        loginWith: {
          oauth: {
            domain: process.env.NEXT_PUBLIC_COGNITO_DOMAIN!,
            scopes: ["openid", "email", "profile"],
            redirectSignIn: [process.env.NEXT_PUBLIC_AUTH_REDIRECT_URL!],
            redirectSignOut: [process.env.NEXT_PUBLIC_AUTH_REDIRECT_URL!],
            responseType: "code",
          },
        },
      },
    },
  });
}

export async function currentSession() {
  if (!authEnabled) {
    return { token: "", username: "K-Quant Owner" };
  }
  const user = await getCurrentUser();
  const session = await fetchAuthSession();
  return {
    token: session.tokens?.idToken?.toString() ?? "",
    username: user.username,
  };
}

export async function login() {
  await signInWithRedirect();
}

export async function logout() {
  await signOut();
}

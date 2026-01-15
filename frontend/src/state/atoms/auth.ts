import { atom } from "recoil";
import type { AuthState } from "../../types";

export const authState = atom<AuthState>({
  key: "authState",
  default: {
    user: null,
    isAuthenticated: false,
    isLoading: true,
  },
});


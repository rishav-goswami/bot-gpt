import type { User, AuthState } from "../../types";

/**
 * Mock authentication service
 * In production, this would connect to a real auth API
 */
class MockAuthService {
  private currentUser: User | null = null;

  /**
   * Mock login - returns a demo user
   */
  async login(email: string, _password: string): Promise<User> {
    // Simulate API delay
    await new Promise((resolve) => setTimeout(resolve, 500));

    // Mock user data
    this.currentUser = {
      id: "demo-user-id",
      email: email || "demo@botconsulting.io",
      created_at: new Date().toISOString(),
    };

    // Store in localStorage
    localStorage.setItem("auth_user", JSON.stringify(this.currentUser));
    localStorage.setItem("auth_token", "mock-jwt-token");

    return this.currentUser;
  }

  /**
   * Mock logout
   */
  async logout(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, 200));
    this.currentUser = null;
    localStorage.removeItem("auth_user");
    localStorage.removeItem("auth_token");
  }

  /**
   * Get current user
   */
  async getCurrentUser(): Promise<User | null> {
    if (this.currentUser) {
      return this.currentUser;
    }

    // Try to restore from localStorage
    const stored = localStorage.getItem("auth_user");
    if (stored) {
      this.currentUser = JSON.parse(stored);
      return this.currentUser;
    }

    return null;
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return !!this.currentUser || !!localStorage.getItem("auth_token");
  }

  /**
   * Initialize auth state (restore from storage)
   */
  async initialize(): Promise<AuthState> {
    const user = await this.getCurrentUser();
    return {
      user,
      isAuthenticated: !!user,
      isLoading: false,
    };
  }
}

export const mockAuthService = new MockAuthService();


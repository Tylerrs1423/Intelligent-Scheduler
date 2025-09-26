'use client';

interface LoginFormProps {
  isSignUp: boolean;
  username: string;
  email: string;
  password: string;
  isLoading: boolean;
  error: string;
  onUsernameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onLogin: (e: React.FormEvent) => void;
  onSignUp: (e: React.FormEvent) => void;
  onGoogleSignIn: () => void;
  onToggleSignUp: () => void;
}

export default function LoginForm({
  isSignUp,
  username,
  email,
  password,
  isLoading,
  error,
  onUsernameChange,
  onEmailChange,
  onPasswordChange,
  onLogin,
  onSignUp,
  onGoogleSignIn,
  onToggleSignUp
}: LoginFormProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-2xl">AF</span>
          </div>
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">
            {isSignUp ? 'Create your account' : 'Welcome back'}
          </h1>
          <p className="text-gray-600">
            {isSignUp ? 'Sign up to get started with AI Foco' : 'Sign in to continue to AI Foco'}
          </p>
        </div>
        
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}
        
        <form onSubmit={isSignUp ? onSignUp : onLogin} className="space-y-4">
          <div>
            <input
              type="text"
              value={username}
              onChange={(e) => onUsernameChange(e.target.value)}
              placeholder={isSignUp ? "Username" : "Username or email"}
              required
              disabled={isLoading}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base transition-colors disabled:opacity-50"
            />
          </div>
          
          {isSignUp && (
            <div>
              <input
                type="email"
                value={email}
                onChange={(e) => onEmailChange(e.target.value)}
                placeholder="Email"
                required
                disabled={isLoading}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base transition-colors disabled:opacity-50"
              />
            </div>
          )}
          
          <div>
            <input
              type="password"
              value={password}
              onChange={(e) => onPasswordChange(e.target.value)}
              placeholder="Password"
              required
              disabled={isLoading}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-base transition-colors disabled:opacity-50"
            />
          </div>
          
          {!isSignUp && (
            <div className="flex justify-end">
              <button
                type="button"
                className="text-blue-600 text-sm font-medium hover:text-blue-700 transition-colors"
              >
                Forgot password?
              </button>
            </div>
          )}
          
          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-blue-500 hover:bg-blue-600 text-white py-3 px-4 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Please wait...' : (isSignUp ? 'Create account' : 'Sign in')}
          </button>
        </form>
        
        <div className="mt-6">
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white text-gray-500">Or continue with</span>
            </div>
          </div>
          
          <div className="mt-6">
            <button
              onClick={onGoogleSignIn}
              disabled={isLoading}
              className="w-full flex justify-center items-center px-4 py-3 border border-gray-300 rounded-lg text-gray-700 bg-white hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Continue with Google
            </button>
          </div>
        </div>
        
        <div className="mt-6 text-center">
          <span className="text-gray-600">
            {isSignUp ? 'Already have an account?' : "Don't have an account?"}
          </span>
          <button
            onClick={onToggleSignUp}
            className="ml-1 text-blue-600 font-medium hover:text-blue-700 transition-colors"
          >
            {isSignUp ? 'Sign in' : 'Sign up'}
          </button>
        </div>
      </div>
    </div>
  );
}

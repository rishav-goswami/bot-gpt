import { createContext, useContext, useState, type ReactNode } from "react";
import { Toast, type ToastProps } from "../../components/ui/Toast";

interface UpdatesContextType {
  showToast: (message: string, type?: ToastProps["type"]) => void;
}

const UpdatesContext = createContext<UpdatesContextType | undefined>(undefined);

export const useUpdates = () => {
  const context = useContext(UpdatesContext);
  if (!context) {
    throw new Error("useUpdates must be used within UpdatesProvider");
  }
  return context;
};

interface UpdatesProviderProps {
  children: ReactNode;
}

export const UpdatesProvider = ({ children }: UpdatesProviderProps) => {
  const [toasts, setToasts] = useState<
    Array<ToastProps & { id: string }>
  >([]);

  const showToast = (message: string, type: ToastProps["type"] = "info") => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, message, type, onClose: () => removeToast(id) }]);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  return (
    <UpdatesContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <Toast key={toast.id} {...toast} />
        ))}
      </div>
    </UpdatesContext.Provider>
  );
};


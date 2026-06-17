import { Sidebar } from "@/components/Sidebar";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-dvh flex bg-surface-secondary">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {children}
      </main>
    </div>
  );
}

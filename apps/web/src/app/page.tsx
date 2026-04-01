export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-xl rounded-3xl border border-white/10 bg-black/20 p-8 backdrop-blur">
        <h1 className="text-4xl font-semibold">OpenGuesser</h1>
        <p className="mt-4 text-white/80">
          Initial monorepo scaffold. Core gameplay modules are implemented in shared packages
          and app-specific components.
        </p>
      </div>
    </main>
  );
}


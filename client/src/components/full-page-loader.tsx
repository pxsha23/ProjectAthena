import { LogoIcon } from '@/components/logo'

export function FullPageLoader({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex h-full min-h-dvh flex-col items-center justify-center gap-3 bg-base">
      <LogoIcon size={48} className="animate-pulse-soft" />
      <span className="text-sm text-subtle">{label}</span>
    </div>
  )
}

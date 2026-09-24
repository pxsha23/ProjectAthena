import { cn } from '@/lib/utils'

/** Slow-drifting colour blobs over a masked dot grid. Purely decorative. */
export function Aurora({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cn('pointer-events-none absolute inset-0 overflow-hidden', className)}>
      <div className="dot-grid absolute inset-0 opacity-60 [mask-image:radial-gradient(ellipse_70%_60%_at_50%_30%,black,transparent)]" />
      <div className="absolute -top-40 left-1/2 h-[28rem] w-[28rem] -translate-x-[85%] animate-drift rounded-full bg-lavender/20 blur-3xl" />
      <div className="absolute -top-24 left-1/2 h-[24rem] w-[24rem] -translate-x-[10%] animate-drift rounded-full bg-mauve/15 blur-3xl [animation-delay:-6s]" />
      <div className="absolute top-40 left-1/2 h-[20rem] w-[20rem] translate-x-[40%] animate-drift rounded-full bg-pink/10 blur-3xl [animation-delay:-12s]" />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-linear-to-b from-transparent to-base" />
    </div>
  )
}

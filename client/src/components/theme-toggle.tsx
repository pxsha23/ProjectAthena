import { Check, Palette } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { THEMES, useTheme, type ThemeId } from '@/lib/theme'
import { cn } from '@/lib/utils'

/**
 * Mini preview of a theme. It sets data-theme on itself, so the token
 * classes inside resolve to that theme's palette.
 */
export function ThemeSwatch({ theme, className }: { theme: ThemeId; className?: string }) {
  return (
    <span
      data-theme={theme}
      aria-hidden="true"
      className={cn('flex size-5 shrink-0 items-center justify-center rounded-full border border-border bg-base', className)}
    >
      <span className="size-2 rounded-full bg-lavender" />
    </span>
  )
}

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme()
  const current = THEMES.find((t) => t.id === theme)

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" className={className} aria-label={`Theme: ${current?.label}. Change theme`}>
          <Palette aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        {THEMES.map((t) => (
          <DropdownMenuItem key={t.id} onSelect={() => setTheme(t.id)} className="items-start py-2">
            <ThemeSwatch theme={t.id} className="mt-0.5" />
            <span className="min-w-0 flex-1">
              <span className="block text-sm text-text">{t.label}</span>
              <span className="block text-xs text-subtle">{t.description}</span>
            </span>
            {theme === t.id && (
              <>
                <Check className="mt-0.5 text-lavender" aria-hidden="true" />
                <span className="sr-only">(selected)</span>
              </>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

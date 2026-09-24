import { AnimatePresence, motion } from 'framer-motion'
import { Menu, X } from 'lucide-react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Logo } from '@/components/logo'
import { SiteLink } from '@/components/site-link'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth'
import { HEADER_LINKS } from '@/lib/site-config'

/** Hamburger button and slide-in panel for the public site on small screens. */
export function MobileNav() {
  const [open, setOpen] = useState(false)
  const { user } = useAuth()
  const close = () => setOpen(false)

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <Button variant="ghost" size="icon-sm" className="md:hidden" aria-label="Open menu">
          <Menu aria-hidden="true" />
        </Button>
      </DialogPrimitive.Trigger>

      <AnimatePresence>
        {open && (
          <DialogPrimitive.Portal forceMount>
            <DialogPrimitive.Overlay asChild forceMount>
              <motion.div
                className="fixed inset-0 z-50 bg-base/70 backdrop-blur-sm md:hidden"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              />
            </DialogPrimitive.Overlay>
            <DialogPrimitive.Content asChild forceMount>
              <motion.div
                className="fixed inset-y-0 right-0 z-50 flex w-[min(20rem,85vw)] flex-col border-l border-border bg-panel p-5 md:hidden"
                initial={{ x: '100%' }}
                animate={{ x: 0 }}
                exit={{ x: '100%' }}
                transition={{ type: 'tween', duration: 0.28, ease: [0.32, 0.72, 0, 1] }}
              >
                <DialogPrimitive.Title className="sr-only">Menu</DialogPrimitive.Title>
                <DialogPrimitive.Description className="sr-only">Site navigation</DialogPrimitive.Description>
                <div className="flex items-center justify-between">
                  <Logo size={24} to="/" />
                  <DialogPrimitive.Close asChild>
                    <Button variant="ghost" size="icon-sm" aria-label="Close menu">
                      <X aria-hidden="true" />
                    </Button>
                  </DialogPrimitive.Close>
                </div>

                <nav aria-label="Main" className="mt-8">
                  <ul className="flex flex-col gap-1">
                    {HEADER_LINKS.map((link, i) => (
                      <motion.li
                        key={link.to}
                        initial={{ opacity: 0, x: 16 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.08 + i * 0.05 }}
                      >
                        <SiteLink
                          link={link}
                          onClick={close}
                          className="block rounded-md px-3 py-2.5 text-base text-muted transition-colors hover:bg-raised hover:text-text"
                        />
                      </motion.li>
                    ))}
                  </ul>
                </nav>

                <div className="mt-auto grid gap-2 border-t border-border pt-5">
                  {user ? (
                    <Button asChild onClick={close}>
                      <Link to="/dashboard">Open dashboard</Link>
                    </Button>
                  ) : (
                    <>
                      <Button asChild variant="secondary" onClick={close}>
                        <Link to="/login">Sign in</Link>
                      </Button>
                      <Button asChild onClick={close}>
                        <Link to="/signup">Get Started</Link>
                      </Button>
                    </>
                  )}
                </div>
              </motion.div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Portal>
        )}
      </AnimatePresence>
    </DialogPrimitive.Root>
  )
}

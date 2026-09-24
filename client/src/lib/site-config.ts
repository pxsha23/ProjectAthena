/**
 * Links used by the public header and footer, kept in one place.
 * Section links start with "/#" so they work from any page.
 */

export interface SiteLink {
  label: string
  to: string
  /** Opens in a new tab (outside the app). */
  external?: boolean
}

export const HEADER_LINKS: SiteLink[] = [
  { label: 'Features', to: '/#agents' },
  { label: 'How it Works', to: '/#how-it-works' },
  { label: 'Docs', to: '/docs' },
  { label: 'About', to: '/about' },
]

/**
 * TODO: replace with the team's real profiles before publishing.
 * These point at the sites' home pages until then.
 */
export const SOCIAL_LINKS = {
  github: 'https://github.com',
  linkedin: 'https://www.linkedin.com',
  email: '',
}

export const FOOTER_COLUMNS: { title: string; links: SiteLink[] }[] = [
  {
    title: 'Product',
    links: [
      { label: 'Features', to: '/#agents' },
      { label: 'How it Works', to: '/#how-it-works' },
      { label: 'Workspace', to: '/#workspace' },
      { label: 'Pricing', to: '/pricing' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'Docs', to: '/docs' },
      { label: 'Research Papers', to: '/research' },
      { label: 'Changelog', to: '/changelog' },
      { label: 'FAQ', to: '/faq' },
    ],
  },
  {
    title: 'Project',
    links: [
      { label: 'About', to: '/about' },
      { label: 'Team', to: '/team' },
      { label: 'Contact', to: '/contact' },
      { label: 'GitHub Repo', to: SOCIAL_LINKS.github, external: true },
    ],
  },
  {
    title: 'Legal',
    links: [
      { label: 'Privacy Policy', to: '/privacy' },
      { label: 'Terms of Service', to: '/terms' },
    ],
  },
]

/** Simple content pages linked from the header and footer. Filled in as the project grows. */
export const INFO_PAGES: Record<string, { title: string; description: string }> = {
  docs: { title: 'Docs', description: 'Guides for every stage of the Athena pipeline, from writing your idea to deploying.' },
  about: {
    title: 'About Athena',
    description:
      'Athena is a final year project: a platform where AI agents take an app idea through spec, tech stack, code, export and deployment, and explain every step.',
  },
  pricing: { title: 'Pricing', description: 'Athena is free to use while it is a student project.' },
  research: { title: 'Research Papers', description: 'The papers and reading behind the multi-agent design of Athena.' },
  changelog: { title: 'Changelog', description: 'What changed in each version of Athena.' },
  faq: { title: 'FAQ', description: 'Answers to common questions about projects, agents and exports.' },
  team: { title: 'Team', description: 'The people building Athena.' },
  contact: { title: 'Contact', description: 'How to reach the Athena team.' },
  privacy: { title: 'Privacy Policy', description: 'How Athena handles your projects and personal data.' },
  terms: { title: 'Terms of Service', description: 'The terms for using Athena.' },
}

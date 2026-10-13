import Link from "next/link";

const LINKS = [
  { href: "/privacy", label: "Privacy policy" },
  { href: "/about", label: "About us" },
  { href: "/faq", label: "FAQ" },
];

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-navy/10 bg-sky">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm sm:px-6 md:flex-row-reverse md:items-center md:justify-between lg:px-8">
        <nav aria-label="Footer">
          <ul className="flex flex-wrap gap-x-2 gap-y-1">
            {LINKS.map(({ href, label }) => (
              <li key={href}>
                <Link
                  href={href}
                  className="inline-flex min-h-11 items-center px-2 font-semibold text-navy underline-offset-4 hover:underline"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <p className="px-2">© {new Date().getFullYear()} HyperStim?</p>
      </div>
    </footer>
  );
}

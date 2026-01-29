"use client";

interface BreadcrumbProps {
  path: string;
  onNavigate: (path: string) => void;
}

export function Breadcrumb({ path, onNavigate }: BreadcrumbProps) {
  const parts = path.split("/").filter(Boolean);

  const breadcrumbs = [
    { name: "/", path: "/" },
    ...parts.map((part, index) => ({
      name: part,
      path: "/" + parts.slice(0, index + 1).join("/"),
    })),
  ];

  return (
    <nav className="flex items-center space-x-2 text-sm">
      {breadcrumbs.map((crumb, index) => (
        <span key={crumb.path} className="flex items-center">
          {index > 0 && (
            <svg
              className="h-4 w-4 text-gray-400 mx-1"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
          )}
          <button
            onClick={() => onNavigate(crumb.path)}
            className={`hover:text-primary-600 ${
              index === breadcrumbs.length - 1
                ? "text-gray-900 font-medium"
                : "text-gray-500"
            }`}
          >
            {crumb.name}
          </button>
        </span>
      ))}
    </nav>
  );
}

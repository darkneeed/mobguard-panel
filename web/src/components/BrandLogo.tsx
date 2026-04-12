import { useEffect, useState } from "react";

type BrandLogoProps = {
  className?: string;
  logoUrl?: string;
  alt?: string;
};

const FALLBACK_LOGO_URL = "/mobguard-cat.png";

export function BrandLogo({ className = "", logoUrl = "", alt = "MobGuard" }: BrandLogoProps) {
  const [currentLogoUrl, setCurrentLogoUrl] = useState(logoUrl || FALLBACK_LOGO_URL);

  useEffect(() => {
    setCurrentLogoUrl(logoUrl || FALLBACK_LOGO_URL);
  }, [logoUrl]);

  return (
    <span className={`brand-mark brand-mark-image ${className}`.trim()}>
      <img
        src={currentLogoUrl}
        alt={alt}
        onError={() => {
          if (currentLogoUrl !== FALLBACK_LOGO_URL) {
            setCurrentLogoUrl(FALLBACK_LOGO_URL);
          }
        }}
      />
    </span>
  );
}

"use client";

import React from "react";

interface CampusLogoProps {
  className?: string;
  variant?: "light" | "dark" | "gold";
  size?: number;
}

export default function CampusLogo({
  className = "h-8 w-8",
  variant = "gold",
  size,
}: CampusLogoProps) {
  // Variant styling for logo icon
  // light = white logo
  // dark = navy/black logo
  // gold = gold logo
  let filterStyle = "";
  if (variant === "light") {
    filterStyle = "brightness-0 invert";
  } else if (variant === "gold") {
    // Converts black PNG icon to golden/yellow color tint
    filterStyle = "brightness-0 invert sepia(1) saturate(5) hue-rotate(5deg)";
  } else if (variant === "dark") {
    // Pure dark/navy tint
    filterStyle = "brightness-0 opacity-90";
  }

  return (
    <img
      src="/logo.png"
      alt="Campus Ops Logo"
      style={size ? { height: size, width: size } : undefined}
      className={`object-contain transition-all ${filterStyle} ${className}`}
    />
  );
}

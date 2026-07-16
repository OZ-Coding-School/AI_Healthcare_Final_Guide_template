"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner, ToasterProps } from "sonner";

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      position="top-right"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg data-[type=error]:!bg-red-500 data-[type=error]:!text-white data-[type=error]:!border-red-600 data-[type=success]:!bg-green-500 data-[type=success]:!text-white data-[type=success]:!border-green-600",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
          error:
            "group-[.toaster]:bg-red-500 group-[.toaster]:text-white group-[.toaster]:border-red-600",
          success:
            "group-[.toaster]:bg-green-500 group-[.toaster]:text-white group-[.toaster]:border-green-600",
          warning:
            "group-[.toaster]:bg-yellow-500 group-[.toaster]:text-white group-[.toaster]:border-yellow-600",
          info: "group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };

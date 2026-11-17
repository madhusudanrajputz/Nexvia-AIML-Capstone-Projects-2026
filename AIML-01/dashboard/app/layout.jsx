import "./globals.css";

export const metadata = {
  title: "AIML-01 | Fraud Analyst",
  description: "Financial fraud detection analyst dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

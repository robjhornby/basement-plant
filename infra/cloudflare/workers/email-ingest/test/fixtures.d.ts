// Vite/vitest `?raw` imports resolve to the file contents as a string.
declare module "*.eml?raw" {
  const content: string;
  export default content;
}

export function Placeholder({ title, text }: { title: string; text: string }) {
  return (
    <div className="content content-narrow">
      <div className="page-head"><h1>{title}</h1></div>
      <p className="muted">{text}</p>
    </div>
  );
}

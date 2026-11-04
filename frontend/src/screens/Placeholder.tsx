import { PageHead } from "../components/PageHead";

export function Placeholder({ title, text }: { title: string; text: string }) {
  return (
    <div className="content content-narrow">
      <PageHead title={title} />
      <p className="muted">{text}</p>
    </div>
  );
}

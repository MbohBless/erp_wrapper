import { Icon } from "@/components/icons";

function IconButton({
  icon,
  title,
  onClick,
  danger,
}: {
  icon: string;
  title: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={`icobtn grid place-items-center w-8 h-8 muted ${
        danger ? "hover:text-err" : "hover:text-accent"
      }`}
    >
      <Icon name={icon} size={16} />
    </button>
  );
}

/** Row-hover action cluster. Buttons render only when their handler is provided. */
export default function RowActions({
  onView,
  onEdit,
  onDelete,
}: {
  onView?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return (
    <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
      {onView && <IconButton icon="eye" title="View" onClick={onView} />}
      {onEdit && <IconButton icon="pencil" title="Edit" onClick={onEdit} />}
      {onDelete && <IconButton icon="trash" title="Delete" danger onClick={onDelete} />}
    </div>
  );
}

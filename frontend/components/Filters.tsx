'use client';

interface FiltersProps {
    radius: number;
    onRadiusChange: (radius: number) => void;
    openNow: boolean;
    onOpenNowChange: (openNow: boolean) => void;
    price: number | undefined;
    onPriceChange: (price: number | undefined) => void;
}

const PRICE_OPTIONS: { value: number | undefined; label: string }[] = [
    { value: undefined, label: "Any" },
    { value: 1, label: "$" },
    { value: 2, label: "$$" },
    { value: 3, label: "$$$" },
    { value: 4, label: "$$$$" },
];

function formatRadius(meters: number): string {
  if (meters < 1000) return `${meters} m`;
  return `${(meters / 1000).toFixed(1).replace(/\.0$/, "")} km`;
}

export default function Filters({
  radius,
  onRadiusChange,
  openNow,
  onOpenNowChange,
  price,
  onPriceChange,
}: FiltersProps) {
  return (
    <div className="flex w-full flex-col gap-4">
      {/* Radius slider */}
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Radius: {formatRadius(radius)}
        </label>
        <input
          type="range"
          min={100}
          max={50000}
          step={100}
          value={radius}
          onChange={(e) => onRadiusChange(Number(e.target.value))}
          className="h-2 w-full cursor-pointer appearance-none rounded-full bg-zinc-200 accent-foreground dark:bg-zinc-700"
        />
        <div className="flex justify-between text-xs text-zinc-400">
          <span>100 m</span>
          <span>50 km</span>
        </div>
      </div>

      {/* Open now + Price row */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Open now checkbox */}
        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            checked={openNow}
            onChange={(e) => onOpenNowChange(e.target.checked)}
            className="h-4 w-4 rounded accent-foreground"
          />
          Open now
        </label>

        {/* Price chips */}
        <div className="flex items-center gap-1">
          <span className="mr-1 text-sm text-zinc-500 dark:text-zinc-400">Price:</span>
          {PRICE_OPTIONS.map(({ value, label }) => (
            <button
              key={label}
              type="button"
              onClick={() => onPriceChange(value)}
              className={
                price === value
                  ? "rounded-full bg-foreground px-3 py-1 text-xs font-medium text-background"
                  : "rounded-full border border-zinc-300 px-3 py-1 text-xs font-medium text-zinc-700 hover:border-zinc-400 dark:border-zinc-600 dark:text-zinc-300 dark:hover:border-zinc-500"
              }
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
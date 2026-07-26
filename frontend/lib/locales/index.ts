// Merges all locale fragments into one flat dictionary per language.
// Each fragment exports `{ en: {...}, fr: {...} }` with namespaced flat keys.
import { common } from "./common";
import { customers } from "./customers";
import { dashboard } from "./dashboard";
import { equipment } from "./equipment";
import { finance } from "./finance";
import { inventory } from "./inventory";
import { maintenance } from "./maintenance";
import { products } from "./products";
import { purchases } from "./purchases";
import { reports } from "./reports";
import { sales } from "./sales";
import { suppliers } from "./suppliers";

const FRAGMENTS = [
  common, reports, dashboard, finance, sales, purchases, products,
  inventory, equipment, maintenance, customers, suppliers,
];

export const DICT = {
  en: Object.assign({}, ...FRAGMENTS.map((f) => f.en)) as Record<string, string>,
  fr: Object.assign({}, ...FRAGMENTS.map((f) => f.fr)) as Record<string, string>,
};

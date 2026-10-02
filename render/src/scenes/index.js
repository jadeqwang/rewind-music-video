// scene registry: shot.scene → module with draw(ctx, localT, globalT, shot, data)
import * as page from './page.js';
import * as suits from './suits.js';
import * as freeze from './freeze.js';
import * as rewind from './rewind.js';
import * as slam from './slam.js';
import * as tree from './tree.js';
import * as black from './black.js';
import * as road from './road.js';
import * as comp from './comp.js';
export const SCENES = { page, suits, freeze, rewind, slam, tree, black, road, comp };

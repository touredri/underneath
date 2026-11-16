import { useState } from 'react';
import { render } from '@testing-library/react';
import { Search } from './Search';

// Test helpers are not counted on the map, even when they use hooks.
function Harness() {
  const [picked, setPicked] = useState(null);
  return <Search onPick={setPicked} />;
}

test('renders', () => {
  render(<Harness />);
});

import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the sidebar with a Capabilities entry point', () => {
  render(<App />);
  const button = screen.getByRole('button', { name: /capabilities/i });
  expect(button).toBeInTheDocument();
});

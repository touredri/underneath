import { Header } from "./components/Header";
import { SearchUsers } from "./components/SearchUsers";

export default function App() {
  return (
    <main>
      <Header title="Team" />
      <SearchUsers />
    </main>
  );
}

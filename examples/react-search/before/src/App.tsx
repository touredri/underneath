import { Header } from "./components/Header";
import { UserList } from "./components/UserList";

export default function App() {
  return (
    <main>
      <Header title="Team" />
      <UserList users={[]} />
    </main>
  );
}

import { Component, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AsistenteChat } from './shared/asistente-chat/asistente-chat';

@Component({
  selector: 'situr-root',
  imports: [RouterOutlet, AsistenteChat],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  protected readonly title = signal('web');
}

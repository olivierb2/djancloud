import { Component, OnInit, OnDestroy, ViewChild, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { Subject, takeUntil, switchMap, filter, first } from 'rxjs';
import { NgIcon } from '@ng-icons/core';
import { FileService, PreviewResponse } from '../../core/services/file.service';
import { Auth } from '../../core/services/auth';
import { UserService } from '../../core/services/user.service';
import { MilkdownEditorComponent } from '../../shared/components/milkdown-editor/milkdown-editor';
import { RoutePaths } from '../../core/constants/routes';

@Component({
  selector: 'app-editor-page',
  standalone: true,
  imports: [CommonModule, NgIcon, MilkdownEditorComponent],
  templateUrl: './editor.html',
  styleUrl: './editor.scss',
})
export class EditorPage implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private fileService = inject(FileService);
  private auth = inject(Auth);
  private userService = inject(UserService);
  private destroy$ = new Subject<void>();

  @ViewChild(MilkdownEditorComponent)
  editorComponent!: MilkdownEditorComponent;

  fileId = 0;
  fileName = '';
  initialContent = '';
  canWrite = false;
  loading = true;
  saving = false;
  connected = false;
  connectedUsers = 0;
  hasUnsavedChanges = false;
  token = '';
  userName = '';
  private parentPath = '';

  protected readonly RoutePaths = RoutePaths;

  ngOnInit(): void {
    this.token = this.auth.getToken() || '';

    this.userService.currentUser$.pipe(
      filter(u => u !== null),
      first(),
      takeUntil(this.destroy$),
    ).subscribe(user => {
      this.userName = user.email;
    });

    this.route.params
      .pipe(
        takeUntil(this.destroy$),
        switchMap(params => {
          this.fileId = +params['fileId'];
          this.loading = true;
          return this.fileService.getPreview(this.fileId);
        }),
      )
      .subscribe({
        next: (preview: PreviewResponse) => {
          this.fileName = preview.display_name;
          this.initialContent = preview.content || '';
          this.canWrite = preview.can_write ?? false;
          this.parentPath = preview.parent_path ?? '';
          this.loading = false;
        },
        error: () => {
          this.loading = false;
          this.router.navigate(['/', RoutePaths.APP, RoutePaths.BROWSE]);
        },
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onContentChanged(): void {
    this.hasUnsavedChanges = true;
  }

  onConnectionStatusChanged(connected: boolean): void {
    this.connected = connected;
  }

  onUsersChanged(count: number): void {
    this.connectedUsers = count;
  }

  save(): void {
    if (!this.editorComponent || this.saving) return;
    this.saving = true;
    const content = this.editorComponent.getMarkdown();
    this.fileService.saveFile(this.fileId, content).subscribe({
      next: () => {
        this.saving = false;
        this.hasUnsavedChanges = false;
      },
      error: () => {
        this.saving = false;
      },
    });
  }

  goBack(): void {
    if (this.parentPath) {
      this.router.navigate(['/', RoutePaths.APP, RoutePaths.BROWSE, this.parentPath]);
    } else {
      this.router.navigate(['/', RoutePaths.APP, RoutePaths.BROWSE]);
    }
  }
}
